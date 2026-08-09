package com.lqq.supportflow.commerce.infrastructure.persistence;

import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.plugins.handler.TenantLineHandler;
import com.baomidou.mybatisplus.extension.plugins.inner.TenantLineInnerInterceptor;
import com.lqq.supportflow.shared.TenantContext;
import net.sf.jsqlparser.expression.Expression;
import net.sf.jsqlparser.expression.LongValue;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class TenantMybatisConfiguration {

    @Bean
    MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        interceptor.addInnerInterceptor(new TenantLineInnerInterceptor(new TenantLineHandler() {
            @Override
            public Expression getTenantId() {
                long tenantId = TenantContext.current()
                        .orElseThrow(() -> new IllegalStateException("tenant context is required for tenant-scoped SQL"))
                        .tenantId();
                return new LongValue(tenantId);
            }

            @Override
            public String getTenantIdColumn() { return "tenant_id"; }

            @Override
            public boolean ignoreTable(String tableName) {
                return switch (tableName) {
                    case "tenants", "users", "tenant_memberships", "refresh_tokens", "flyway_schema_history" -> true;
                    default -> false;
                };
            }
        }));
        return interceptor;
    }
}
