package com.lqq.supportflow.shared;

import java.util.concurrent.Executor;
import java.util.concurrent.Executors;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;

@Configuration
@EnableAsync
public class AsyncConfiguration {
    @Bean(destroyMethod = "close")
    Executor generationExecutor() { return Executors.newVirtualThreadPerTaskExecutor(); }
}
