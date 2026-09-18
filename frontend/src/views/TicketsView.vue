<script setup>
import {computed, onMounted, ref, watch} from 'vue';
import {Bot, CheckCircle2, Clock3, RefreshCcw, Send} from '@lucide/vue';
import {
  addTicketComment,
  assignTicket,
  changeTicketStatus,
  claimTicket,
  getAssignableMembers,
  getTicketComments,
  getTicketContext,
  sendAgentReply,
} from '../api.js';
import {currencyAmount, formatDateTime} from '../lib/format.js';
import AppButton from '../components/AppButton.vue';
import PageHeader from '../components/PageHeader.vue';

const props = defineProps({
  tickets: {type: Array, default: () => []},
});
const emit = defineEmits(['notice', 'ticket-updated']);
const selected = defineModel('selected', {type: Object, default: null});

const comments = ref([]);
const ticketContext = ref(null);
const comment = ref('');
const composerMode = ref('note');
const pending = ref(false);
const members = ref([]);
const targetMember = ref('');
// 同一工单的认领请求复用同一个幂等键，重复点击不会产生第二次认领。
const claimKeys = new Map();
const replyKeys = new Map();
const activeTicketFilter = ref('all');

const notify = message => emit('notice', message);
const conversationMessages = computed(() => ticketContext.value?.conversation?.messages || []);
const conversationTraces = computed(() => ticketContext.value?.conversation?.traces || []);
const relatedOrder = computed(() => ticketContext.value?.orders?.[0] || null);
const canClaim = computed(() => Boolean(selected.value) && !selected.value.assignedMembershipId && selected.value.statusCode === 'NEW');
const canResolve = computed(() => Boolean(selected.value) && ['OPEN', 'PENDING_CUSTOMER', 'PENDING_APPROVAL'].includes(selected.value.statusCode));
const canClose = computed(() => selected.value?.statusCode === 'RESOLVED');
const visibleTickets = computed(() => props.tickets.filter(ticket => {
  if (activeTicketFilter.value === 'unassigned') return !ticket.assignedMembershipId;
  if (activeTicketFilter.value === 'priority') return ['高', '紧急'].includes(ticket.priority);
  return true;
}));

const loadDetail = () => {
  if (!selected.value?.rawId) return;
  Promise.all([getTicketComments(selected.value.rawId), getTicketContext(selected.value.rawId)])
    .then(([loadedComments, loadedContext]) => {
      comments.value = loadedComments;
      ticketContext.value = loadedContext;
    })
    .catch(error => notify(error.message));
};

watch(() => selected.value?.rawId, loadDetail, {immediate: true});

onMounted(() => {
  getAssignableMembers().then(items => {
    members.value = items;
    targetMember.value = targetMember.value || items[0]?.membershipId || '';
  }).catch(error => notify(error.message));
});

// 归一化与列表替换留在父级，这里只上报原始响应。
const updateTicket = updated => emit('ticket-updated', updated);

const act = async (action, success) => {
  if (!selected.value || pending.value) return;
  pending.value = true;
  try {
    updateTicket(await action(selected.value.rawId));
    notify(success);
  } catch (error) {
    notify(error.message);
  } finally {
    pending.value = false;
  }
};

const sendComment = async () => {
  const content = comment.value.trim();
  if (!content || !selected.value || pending.value) return;
  pending.value = true;
  try {
    const added = await addTicketComment(selected.value.rawId, content);
    comments.value = [...comments.value, added];
    comment.value = '';
    notify('内部备注已保存。');
  } catch (error) {
    notify(error.message);
  } finally {
    pending.value = false;
  }
};

const sendReply = async () => {
  const content = comment.value.trim();
  if (!content || !selected.value || pending.value) return;
  pending.value = true;
  try {
    const ticketId = selected.value.rawId;
    const key = replyKeys.get(ticketId) || crypto.randomUUID();
    replyKeys.set(ticketId, key);
    await sendAgentReply(ticketId, content, key);
    replyKeys.delete(ticketId);
    comment.value = '';
    await loadDetail();
    notify('正式回复已发送给消费者。');
  } catch (error) {
    notify(error.message);
  } finally {
    pending.value = false;
  }
};

const claimSelected = ticketId => {
  const key = claimKeys.get(ticketId) || crypto.randomUUID();
  claimKeys.set(ticketId, key);
  return claimTicket(ticketId, key).then(result => {
    claimKeys.delete(ticketId);
    return result;
  });
};

const refreshDetail = () => {
  Promise.all([getTicketComments(selected.value.rawId), getTicketContext(selected.value.rawId)])
    .then(([loadedComments, loadedContext]) => {
      comments.value = loadedComments;
      ticketContext.value = loadedContext;
      notify('会话与处理记录已刷新。');
    })
    .catch(error => notify(error.message));
};
</script>

<template>
  <template v-if="!selected">
    <PageHeader title="工单协同" sub="当前没有可处理工单" />
    <p class="empty-state">当前没有工单。</p>
  </template>
  <template v-else>
    <PageHeader title="工单协同" :sub="`我的工单 · ${visibleTickets.length} 个待处理`" />
    <div class="ticket-layout">
      <section class="panel ticket-list">
        <div class="tabs compact">
          <button :class="{selected: activeTicketFilter === 'all'}" @click="activeTicketFilter = 'all'">全部工单 <b>{{ tickets.length }}</b></button>
          <button :class="{selected: activeTicketFilter === 'unassigned'}" @click="activeTicketFilter = 'unassigned'">未分配</button>
          <button :class="{selected: activeTicketFilter === 'priority'}" @click="activeTicketFilter = 'priority'">高优先级</button>
        </div>
        <button
          v-for="ticket in visibleTickets"
          :key="ticket.id"
          :class="selected.id === ticket.id ? 'ticket-item selected' : 'ticket-item'"
          @click="selected = ticket"
        >
          <div class="ticket-top">
            <strong>{{ ticket.id }}</strong>
            <span :class="ticket.priority === '紧急' ? 'priority danger' : 'priority'">{{ ticket.priority }}</span>
          </div>
          <p>{{ ticket.title }}</p>
          <small>{{ ticket.customer }} · {{ ticket.sla }}</small>
        </button>
      </section>
      <section class="panel conversation">
        <div class="conversation-head">
          <div>
            <h2>{{ selected.title }}</h2>
            <span>{{ selected.id }} · {{ selected.status }} · 优先级 {{ selected.priority }}</span>
          </div>
          <span class="sla-badge"><Clock3 :size="15" /> {{ selected.sla }}</span>
        </div>
        <div class="conversation-body">
          <div
            v-for="(item, index) in conversationMessages"
            :key="`${item.createdAt}-${index}`"
            :class="['AI', 'AGENT'].includes(item.senderType) ? 'message ai' : 'message customer'"
          >
            <span class="message-avatar"><Bot v-if="item.senderType === 'AI'" :size="17" /><template v-else>客</template></span>
            <div>
              <small>{{ item.senderType === 'AI' ? 'SupportFlow AI' : item.senderType === 'AGENT' ? '客服坐席' : selected.customer }} · {{ formatDateTime(item.createdAt) }}</small>
              <p>{{ item.content }}</p>
            </div>
          </div>
          <div
            v-for="(trace, index) in conversationTraces"
            :key="`${trace.generationId}-${trace.type}-${index}`"
            class="message note"
          >
            <span class="message-avatar">轨</span>
            <div>
              <small>生成轨迹 · {{ trace.type }}</small>
              <p>{{ trace.type === 'knowledge.citations' ? '已记录租户知识引用证据' : '已记录工具调用与结果' }}</p>
            </div>
          </div>
          <div v-for="item in comments" :key="item.id" class="message note">
            <span class="message-avatar">内</span>
            <div>
              <small>坐席备注 · {{ formatDateTime(item.createdAt) }}</small>
              <p>{{ item.content }}</p>
            </div>
          </div>
          <p v-if="!conversationMessages.length && !comments.length" class="empty-state">正在加载会话详情…</p>
        </div>
        <div class="composer">
          <div class="composer-tabs">
            <button :class="{selected: composerMode === 'note'}" @click="composerMode = 'note'">内部备注</button>
            <button :class="['ai-link', {selected: composerMode === 'reply'}]" @click="composerMode = 'reply'"><Bot :size="15" /> 正式回复</button>
          </div>
          <textarea v-model="comment" :aria-label="composerMode === 'note' ? '内部备注' : '正式回复'" :placeholder="composerMode === 'note' ? '记录仅供内部查看的处理信息…' : '向消费者发送处理结果…'" :disabled="pending"></textarea>
          <div class="composer-actions">
            <AppButton v-if="canClaim" primary @click="act(claimSelected, '工单已认领，现可继续处理。')">{{ pending ? '处理中…' : '认领工单' }}</AppButton>
            <AppButton primary :icon="Send" :disabled="pending || (composerMode === 'reply' && !selected.assignedMembershipId)" @click="composerMode === 'note' ? sendComment() : sendReply()">{{ pending ? '处理中…' : composerMode === 'note' ? '保存内部备注' : '发送正式回复' }}</AppButton>
            <AppButton v-if="canResolve" @click="act(ticketId => changeTicketStatus(ticketId, 'RESOLVED'), '工单已标记为已解决。')">标记已解决</AppButton>
            <AppButton v-if="canClose" @click="act(ticketId => changeTicketStatus(ticketId, 'CLOSED'), '工单已关闭。')">关闭工单</AppButton>
          </div>
        </div>
      </section>
      <aside class="panel context-panel">
        <h2>客户与订单</h2>
        <div class="profile">
          <div class="profile-avatar">客</div>
          <div><strong>{{ selected.customer }}</strong><small>消费者服务工单</small></div>
        </div>
        <div class="context-block">
          <span>关联订单</span>
          <strong>{{ relatedOrder?.orderNo || '暂无订单' }}</strong>
          <small>{{ relatedOrder ? `${currencyAmount(relatedOrder.totalAmount, relatedOrder.currency)} · ${relatedOrder.status}` : '未关联消费者订单' }}</small>
        </div>
        <div class="context-block">
          <span>工单状态</span>
          <strong>{{ selected.status }}</strong>
          <small>{{ selected.assignedMembershipId ? '已分配给坐席' : '等待坐席认领' }}</small>
        </div>
        <div class="context-block">
          <label for="ticket-assignee">转派坐席</label>
          <select id="ticket-assignee" v-model="targetMember" class="field-input" :disabled="pending || !members.length">
            <option v-for="member in members" :key="member.membershipId" :value="member.membershipId">{{ member.displayName }} · {{ member.role }}</option>
          </select>
          <AppButton
            :disabled="pending || !targetMember"
            @click="act(ticketId => assignTicket(ticketId, targetMember), '工单已转派并记录审计。')"
          >确认转派</AppButton>
        </div>
        <h3>处理提示</h3>
        <div class="evidence-line"><CheckCircle2 />先核对订单与知识库依据</div>
        <div class="evidence-line"><CheckCircle2 />退款与补偿仍需走审批流程</div>
        <AppButton :icon="RefreshCcw" @click="refreshDetail">刷新处理记录</AppButton>
      </aside>
    </div>
  </template>
</template>
