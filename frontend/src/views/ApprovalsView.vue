<script setup>
import {onMounted, ref} from 'vue';
import {AlertTriangle, CheckCircle2, ChevronDown} from '@lucide/vue';
import {decideApproval, getApprovals} from '../api.js';
import {approvalActionLabel, approvalStatusClass, approvalStatusLabel, currencyAmount, formatDateTime} from '../lib/format.js';
import AppButton from '../components/AppButton.vue';
import PageHeader from '../components/PageHeader.vue';

const emit = defineEmits(['notice']);

const approvals = ref([]);
const selectedApproval = ref(null);
const pending = ref(false);
// 同一审批的同一决策复用同一个幂等键，失败重试不会产生第二次业务效果。
const idempotencyKeys = new Map();

onMounted(() => {
  getApprovals().then(items => {
    approvals.value = items;
    selectedApproval.value = items[0] || null;
  }).catch(error => emit('notice', error.message));
});

const decide = async decision => {
  if (!selectedApproval.value || selectedApproval.value.status !== 'PENDING' || pending.value) return;
  pending.value = true;
  try {
    const current = selectedApproval.value;
    const keyId = `${current.id}:${decision}`;
    const idempotencyKey = idempotencyKeys.get(keyId) || crypto.randomUUID();
    idempotencyKeys.set(keyId, idempotencyKey);
    const updated = await decideApproval(current.id, decision, idempotencyKey);
    approvals.value = approvals.value.map(item => (item.id === updated.id ? updated : item));
    selectedApproval.value = updated;
    idempotencyKeys.delete(keyId);
    emit('notice', decision === 'APPROVED' ? '审批已批准，已创建后续执行任务。' : '审批已拒绝。');
  } catch (error) {
    emit('notice', error.message);
  } finally {
    pending.value = false;
  }
};
</script>

<template>
  <PageHeader title="高风险操作审批" sub="退款与补偿需要主管确认后执行">
    <AppButton>全部申请 <ChevronDown :size="14" /></AppButton>
  </PageHeader>
  <div class="tabs">
    <button class="selected">待我审批 <b>{{ approvals.filter(item => item.status === 'PENDING').length }}</b></button>
    <button>全部申请</button>
    <button>执行记录</button>
  </div>
  <div class="approval-layout">
    <section class="panel table-panel">
      <table>
        <thead>
          <tr><th>申请编号</th><th>操作</th><th>订单</th><th>金额</th><th>状态</th><th>到期时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in approvals" :key="item.id" @click="selectedApproval = item">
            <td><strong>APR-{{ item.id }}</strong></td>
            <td>{{ approvalActionLabel(item.actionType) }}</td>
            <td>{{ item.orderNo }}</td>
            <td>{{ currencyAmount(item.amount, item.currency) }}</td>
            <td><span :class="`status ${approvalStatusClass(item.status)}`">{{ approvalStatusLabel(item.status) }}</span></td>
            <td>{{ formatDateTime(item.expiresAt) }}</td>
          </tr>
          <tr v-if="!approvals.length"><td colspan="6">当前没有审批申请</td></tr>
        </tbody>
      </table>
    </section>
    <aside class="panel approval-detail">
      <template v-if="selectedApproval">
        <div class="panel-head">
          <h2>{{ approvalActionLabel(selectedApproval.actionType) }}详情</h2>
          <span :class="`status ${approvalStatusClass(selectedApproval.status)}`">{{ approvalStatusLabel(selectedApproval.status) }}</span>
        </div>
        <p class="detail-label">APR-{{ selectedApproval.id }} · v{{ selectedApproval.version }}</p>
        <div class="approval-summary">
          <strong>{{ selectedApproval.actionSummary }}</strong>
          <span>订单：{{ selectedApproval.orderNo }}</span>
          <span>金额：{{ currencyAmount(selectedApproval.amount, selectedApproval.currency) }}</span>
          <span>资格证据：{{ selectedApproval.eligibilityEvidence }}</span>
          <span>申请人：{{ selectedApproval.requestedByMembershipId ? `成员 ${selectedApproval.requestedByMembershipId}` : 'AI 工作流' }}</span>
          <span>操作人：{{ selectedApproval.decidedByMembershipId ? `成员 ${selectedApproval.decidedByMembershipId}` : '尚未处理' }}</span>
          <small>到期时间：{{ formatDateTime(selectedApproval.expiresAt) }}</small>
        </div>
        <h3>审核提示</h3>
        <div class="evidence-line"><CheckCircle2 />请核对订单、金额和退款资格</div>
        <div class="evidence-line"><CheckCircle2 />批准后只会创建可靠执行任务</div>
        <textarea placeholder="审批意见（可选）"></textarea>
        <label class="check"><input type="checkbox" /> 我已核对业务依据和操作范围</label>
        <div class="approval-actions">
          <AppButton @click="decide('REJECTED')">{{ pending ? '处理中…' : '拒绝申请' }}</AppButton>
          <AppButton primary @click="decide('APPROVED')">{{ pending ? '处理中…' : '批准申请' }}</AppButton>
        </div>
        <p class="warning"><AlertTriangle :size="15" />批准不会在当前页面直接执行退款，后续处理由 Outbox 和消息消费者完成。</p>
      </template>
      <p v-else>选择一条审批申请查看详情。</p>
    </aside>
  </div>
</template>
