<script setup>
import {computed} from 'vue';
import {ArrowRight, CalendarDays, ExternalLink, ShieldCheck, SlidersHorizontal} from '@lucide/vue';
import AppButton from '../components/AppButton.vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';

const props = defineProps({
  overview: {type: Object, default: null},
  tickets: {type: Array, default: () => []},
});
const emit = defineEmits(['nav']);

const go = key => emit('nav', key);
const todayLabel = new Intl.DateTimeFormat('zh-CN', {year: 'numeric', month: 'long', day: 'numeric'}).format(new Date());

const metrics = computed(() => props.overview || {
  completedGenerations: 0,
  handoffGenerations: 0,
  aiResolutionRate: 0,
  overdueTickets: 0,
  inputTokens: 0,
  outputTokens: 0,
  averageGenerationLatencyMs: 0,
});
</script>

<template>
  <PageHeader title="工作台总览" sub="实时掌握客服、知识库和 SLA 运行情况">
    <AppButton :icon="CalendarDays">今日 · {{ todayLabel }}</AppButton>
    <AppButton :icon="ExternalLink" disabled>导出报告</AppButton>
  </PageHeader>
  <div class="stats">
    <StatCard label="AI 已解决" :value="metrics.completedGenerations.toLocaleString()" :delta="`转人工 ${metrics.handoffGenerations.toLocaleString()} 次`" />
    <StatCard label="AI 解决率" :value="`${(metrics.aiResolutionRate * 100).toFixed(1)}%`" delta="按已完成生成统计" tone="warn" />
    <StatCard label="模型 Token" :value="(metrics.inputTokens + metrics.outputTokens).toLocaleString()" :delta="`平均延迟 ${metrics.averageGenerationLatencyMs} ms`" />
    <StatCard label="SLA 风险" :value="metrics.overdueTickets.toLocaleString()" delta="仍未解决的逾期工单" tone="danger" />
  </div>
  <div class="grid two">
    <section class="panel chart-panel">
      <div class="panel-head">
        <h2>客服会话趋势</h2>
        <span class="status">暂无日趋势接口</span>
      </div>
      <div class="empty-state chart-empty">
        <strong>暂无可核验的趋势数据</strong>
        <span>当前接口只提供租户累计运营指标，未提供按天聚合数据，因此不展示模拟曲线。</span>
      </div>
    </section>
    <section class="panel">
      <div class="panel-head">
        <h2>SLA 风险工单</h2>
        <button class="text-link" @click="go('tickets')">查看全部 <ArrowRight :size="14" /></button>
      </div>
      <div v-for="ticket in props.tickets.slice(0, 3)" :key="ticket.id" class="risk-row">
        <div><strong>{{ ticket.id }}</strong><span>{{ ticket.title }}</span></div>
        <em :class="ticket.priority === '紧急' ? 'danger' : ''">{{ ticket.priority }}</em>
        <small>{{ ticket.sla }}</small>
      </div>
    </section>
  </div>
  <div class="grid three">
    <section class="panel">
      <div class="panel-head">
        <h2>知识库健康度</h2>
        <button class="text-link" @click="go('knowledge')">管理知识库</button>
      </div>
      <div class="health-big"><ShieldCheck /><strong>以知识库页面为准</strong><span>当前总览接口尚未提供租户级文档与切片统计。</span></div>
      <p class="empty-state">不使用静态数量，点击“管理知识库”查看实际导入状态。</p>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>RAG 检索质量</h2><SlidersHorizontal :size="17" /></div>
      <div class="quality">
        <div><strong>—</strong><span>平均相关性</span></div>
        <div><strong>—</strong><span>引用覆盖率</span></div>
        <div><strong>—</strong><span>无证据回答率</span></div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>最近活动</h2></div>
      <p class="empty-state">活动审计接口尚未开放，避免展示固定示例数据。</p>
    </section>
  </div>
</template>
