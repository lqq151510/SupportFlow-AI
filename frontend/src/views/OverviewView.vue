<script setup>
import {computed} from 'vue';
import {ArrowRight, CheckCircle2, ChevronDown, ExternalLink, FileText, ShieldCheck, SlidersHorizontal, Ticket} from '@lucide/vue';
import ActivityRow from '../components/ActivityRow.vue';
import AppButton from '../components/AppButton.vue';
import PageHeader from '../components/PageHeader.vue';
import StatCard from '../components/StatCard.vue';

const props = defineProps({
  overview: {type: Object, default: null},
  tickets: {type: Array, default: () => []},
});
const emit = defineEmits(['nav']);

const go = key => emit('nav', key);

const metrics = computed(() => props.overview || {
  completedGenerations: 1284,
  handoffGenerations: 86,
  aiResolutionRate: .942,
  overdueTickets: 7,
  inputTokens: 0,
  outputTokens: 0,
  averageGenerationLatencyMs: 0,
});
</script>

<template>
  <PageHeader title="工作台总览" sub="实时掌握客服、知识库和 SLA 运行情况">
    <AppButton>今日 · 2026年8月9日 <ChevronDown :size="14" /></AppButton>
    <AppButton :icon="ExternalLink">导出报告</AppButton>
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
        <div class="legend"><i class="cyan"></i>AI 自动处理 <i class="violet"></i>转人工</div>
      </div>
      <div class="chart">
        <div class="chart-grid"></div>
        <svg viewBox="0 0 600 210" preserveAspectRatio="none">
          <polyline points="0,150 70,122 140,138 210,72 280,94 350,55 420,82 490,32 560,50 600,20" fill="none" stroke="#20b9d8" stroke-width="4" />
          <polyline points="0,188 70,166 140,180 210,142 280,156 350,132 420,145 490,110 560,122 600,102" fill="none" stroke="#7564ee" stroke-width="4" />
        </svg>
        <div class="axis">
          <span>周一</span><span>周二</span><span>周三</span><span>周四</span><span>周五</span><span>周六</span><span>周日</span>
        </div>
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
      <div class="health-big"><CheckCircle2 /><strong>健康</strong><span>248 份文档 · 1,240 个切片</span></div>
      <div class="progress large"><span :style="{width: '92%'}"></span></div>
      <div class="split-note"><span>已索引 <b>244</b></span><span>处理中 <b>3</b></span><span>失败 <b class="danger">1</b></span></div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>RAG 检索质量</h2><SlidersHorizontal :size="17" /></div>
      <div class="quality">
        <div><strong>0.86</strong><span>平均相关性</span></div>
        <div><strong>94.2%</strong><span>引用覆盖率</span></div>
        <div><strong>3.8%</strong><span>无证据回答率</span></div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>最近活动</h2><button class="text-link">查看日志</button></div>
      <ActivityRow text="退款与退货政策已重新索引" time="2 分钟前" :icon="FileText" />
      <ActivityRow text="TKT-52418 已分配给坐席 A" time="12 分钟前" :icon="Ticket" />
      <ActivityRow text="退款审批申请待处理" time="26 分钟前" :icon="ShieldCheck" />
    </section>
  </div>
</template>
