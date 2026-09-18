<script setup>
import {computed} from 'vue';

const props = defineProps({
  overview: {type: Object, default: null},
});

const integer = value => Number(value || 0).toLocaleString();
const percent = value => `${(Number(value || 0) * 100).toFixed(1)}%`;

const data = computed(() => props.overview || {
  completedGenerations: 0,
  handoffGenerations: 0,
  aiResolutionRate: 0,
  overdueTickets: 0,
  inputTokens: 0,
  outputTokens: 0,
  averageGenerationLatencyMs: 0,
});
const terminal = computed(() => Number(data.value.completedGenerations) + Number(data.value.handoffGenerations));
const handoffRate = computed(() => (terminal.value ? Number(data.value.handoffGenerations) / terminal.value : 0));
const inputShare = computed(() => Math.min(100, Number(data.value.inputTokens) / Math.max(1, Number(data.value.inputTokens) + Number(data.value.outputTokens)) * 100));
const outputShare = computed(() => Math.min(100, Number(data.value.outputTokens) / Math.max(1, Number(data.value.inputTokens) + Number(data.value.outputTokens)) * 100));
</script>

<template>
  <div class="page-header">
    <div><h1>SLA 与运营报表</h1><p>来自当前租户真实生成任务与工单数据</p></div>
  </div>
  <div class="stats">
    <div class="stat"><span>AI 已解决</span><strong>{{ integer(data.completedGenerations) }}</strong><small>已完成生成任务</small></div>
    <div class="stat"><span>AI 解决率</span><strong>{{ percent(data.aiResolutionRate) }}</strong><small>按终态生成统计</small></div>
    <div class="stat"><span>转人工率</span><strong>{{ percent(handoffRate) }}</strong><small>{{ integer(data.handoffGenerations) }} 次转人工</small></div>
    <div class="stat"><span>SLA 违规工单</span><strong class="danger">{{ integer(data.overdueTickets) }}</strong><small>未解决且已逾期</small></div>
  </div>
  <div class="grid two">
    <section class="panel">
      <div class="panel-head"><h2>模型用量</h2><span class="status success">租户隔离</span></div>
      <div class="quality vertical">
        <div>
          <span>输入 Token</span><strong>{{ integer(data.inputTokens) }}</strong>
          <div class="progress"><span :style="{width: `${inputShare}%`}"></span></div>
        </div>
        <div>
          <span>输出 Token</span><strong>{{ integer(data.outputTokens) }}</strong>
          <div class="progress purple"><span :style="{width: `${outputShare}%`}"></span></div>
        </div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>生成性能</h2></div>
      <div class="health-big"><strong>{{ integer(data.averageGenerationLatencyMs) }} ms</strong><span>平均模型生成延迟</span></div>
      <p class="safe-note">统计只包含已记录 latency_ms 的生成任务，不混入静态演示数据。</p>
    </section>
  </div>
</template>
