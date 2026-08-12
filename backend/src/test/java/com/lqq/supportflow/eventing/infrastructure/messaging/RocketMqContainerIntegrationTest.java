package com.lqq.supportflow.eventing.infrastructure.messaging;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.PublishedOutboxEvent;
import com.lqq.supportflow.eventing.domain.OutboxEvent;
import com.lqq.supportflow.shared.TenantContext;
import java.net.ServerSocket;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.apache.rocketmq.client.producer.DefaultMQProducer;
import org.springframework.context.ApplicationEventPublisher;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.Network;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.images.builder.Transferable;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers(disabledWithoutDocker = true)
class RocketMqContainerIntegrationTest {

    private static final DockerImageName ROCKETMQ = DockerImageName.parse("apache/rocketmq:5.3.2");

    @Test
    void publishesAndConsumesARealRocketMqEventWithTenantContext() throws Exception {
        int brokerPort = availablePort();
        String brokerConfig = """
                brokerClusterName=DefaultCluster
                brokerName=broker-it
                brokerId=0
                listenPort=%d
                namesrvAddr=rocketmq-namesrv:9876
                autoCreateTopicEnable=false
                brokerIP1=127.0.0.1
                """.formatted(brokerPort);

        try (Network network = Network.newNetwork();
                GenericContainer<?> nameserver = new GenericContainer<>(ROCKETMQ)
                        .withNetwork(network)
                        .withNetworkAliases("rocketmq-namesrv")
                        .withEnv("JAVA_OPT_EXT", "-Xms128m -Xmx128m")
                        .withCommand("sh", "mqnamesrv")
                        .withExposedPorts(9876)
                        .waitingFor(Wait.forListeningPort().withStartupTimeout(Duration.ofMinutes(2)));
                GenericContainer<?> broker = new GenericContainer<>(ROCKETMQ)
                .withNetwork(network)
                .withNetworkAliases("rocketmq-broker")
                .withEnv("JAVA_OPT_EXT", "-Xms256m -Xmx256m -Xmn128m")
                .withCopyToContainer(Transferable.of(brokerConfig), "/tmp/supportflow-broker.conf")
                .withCommand("sh", "mqbroker", "-n", "rocketmq-namesrv:9876", "-c", "/tmp/supportflow-broker.conf")
                .withExposedPorts(brokerPort)
                .waitingFor(Wait.forLogMessage(".*The broker\\[.*\\] boot success.*\\n", 1)
                        .withStartupTimeout(Duration.ofMinutes(3)))) {
            nameserver.start();
            broker.setPortBindings(List.of(brokerPort + ":" + brokerPort));
            broker.start();

            String nameserverAddress = nameserver.getHost() + ":" + nameserver.getMappedPort(9876);
            String topic = "supportflow-it-" + System.nanoTime();
            var topicCreation = broker.execInContainer("sh", "mqadmin", "updateTopic",
                    "-n", "rocketmq-namesrv:9876", "-b", "127.0.0.1:" + brokerPort,
                    "-t", topic, "-r", "2", "-w", "2");
            assertThat(topicCreation.getExitCode()).as(topicCreation.getStderr()).isZero();
            assertThat(topicCreation.getStdout()).as(topicCreation.getStderr()).contains("create topic to");
            awaitTopicRoute(nameserverAddress, topic);
            CountDownLatch consumed = new CountDownLatch(1);
            AtomicReference<PublishedOutboxEvent> received = new AtomicReference<>();
            AtomicReference<Long> tenantDuringPublish = new AtomicReference<>();
            ApplicationEventPublisher publisher = event -> {
                if (event instanceof PublishedOutboxEvent published) {
                    received.set(published);
                    tenantDuringPublish.set(TenantContext.current().orElseThrow().tenantId());
                    consumed.countDown();
                }
            };
            ObjectMapper json = new ObjectMapper().findAndRegisterModules();
            RocketMqSpringEventConsumer consumer = new RocketMqSpringEventConsumer(
                    json, publisher, nameserverAddress, topic, "supportflow-it-consumer-" + System.nanoTime(), 2);
            RocketMqOutboxDeliveryGateway producer = new RocketMqOutboxDeliveryGateway(
                    json, nameserverAddress, topic);

            try {
                consumer.start();
                producer.start();
                producer.publish(new OutboxEvent(
                        41L, 73L, "approval.approved", "approval", "91", "{\"approved\":true}", 0, Instant.now()));

                assertThat(consumed.await(30, TimeUnit.SECONDS)).isTrue();
                assertThat(received.get()).isEqualTo(new PublishedOutboxEvent(
                        41L, 73L, "approval.approved", "{\"approved\":true}"));
                assertThat(tenantDuringPublish.get()).isEqualTo(73L);
                assertThat(TenantContext.current()).isEmpty();
            } finally {
                producer.stop();
                consumer.stop();
            }
        }
    }

    private int availablePort() throws Exception {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        }
    }

    private void awaitTopicRoute(String nameserverAddress, String topic) throws Exception {
        DefaultMQProducer probe = new DefaultMQProducer("supportflow-it-route-probe-" + System.nanoTime());
        probe.setNamesrvAddr(nameserverAddress);
        probe.start();
        try {
            Exception lastFailure = null;
            for (int attempt = 0; attempt < 60; attempt++) {
                try {
                    if (!probe.fetchPublishMessageQueues(topic).isEmpty()) return;
                } catch (Exception exception) {
                    // NameServer registration is asynchronous after explicit topic creation.
                    lastFailure = exception;
                }
                Thread.sleep(500);
            }
            throw new IllegalStateException("RocketMQ topic route did not become visible: " + topic, lastFailure);
        } finally {
            probe.shutdown();
        }
    }
}
