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
                autoCreateTopicEnable=true
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
                .waitingFor(Wait.forListeningPort().withStartupTimeout(Duration.ofMinutes(3)))) {
            nameserver.start();
            broker.setPortBindings(List.of(brokerPort + ":" + brokerPort));
            broker.start();

            String nameserverAddress = nameserver.getHost() + ":" + nameserver.getMappedPort(9876);
            String topic = "supportflow-it-" + System.nanoTime();
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
            ObjectMapper json = new ObjectMapper();
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
}
