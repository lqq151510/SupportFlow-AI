<script setup>
import {onMounted, ref} from 'vue';
import {Bot, Send, ShieldCheck} from '@lucide/vue';
import {createConversation, getCustomerOrders, readGenerationEvents, submitCustomerMessage} from '../api.js';
import {currencyAmount, formatDateTime} from '../lib/format.js';
import AppButton from '../components/AppButton.vue';
import PageHeader from '../components/PageHeader.vue';

const orders = ref([]);
const selectedOrder = ref(null);
const error = ref('');
const message = ref('');
const messages = ref([]);
const generating = ref(false);
// 同一会话复用同一个 conversationId，避免每条消息都新建会话。
let conversationId = null;

onMounted(() => {
  getCustomerOrders().then(items => {
    orders.value = items;
    selectedOrder.value = items[0] || null;
  }).catch(loadError => {error.value = loadError.message;});
});

const poll = async generationId => {
  let lastEventId;
  for (let attempt = 0; attempt < 40; attempt++) {
    const events = await readGenerationEvents(generationId, lastEventId);
    for (const event of events) {
      lastEventId = event.id || lastEventId;
      if (event.type === 'text.delta') {
        const items = messages.value;
        const last = items.at(-1);
        messages.value = last?.role === 'assistant'
          ? [...items.slice(0, -1), {...last, content: last.content + event.data.text}]
          : [...items, {role: 'assistant', content: event.data.text || ''}];
      }
      if (event.type === 'generation.reset') {
        const items = messages.value;
        messages.value = items.at(-1)?.role === 'assistant' ? items.slice(0, -1) : items;
      }
      if (event.type === 'handoff.required') {
        messages.value = [...messages.value, {role: 'system', content: '已转人工客服，坐席会继续处理该问题。'}];
      }
      if (event.type === 'model.completed' || event.type === 'handoff.required') return;
    }
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  throw new Error('生成进度暂未完成，请稍后重试。');
};

const send = async event => {
  event.preventDefault();
  const content = message.value.trim();
  if (!content || generating.value) return;
  error.value = '';
  generating.value = true;
  messages.value = [...messages.value, {role: 'customer', content}];
  message.value = '';
  try {
    if (!conversationId) conversationId = (await createConversation()).id;
    const generation = await submitCustomerMessage(conversationId, content, crypto.randomUUID());
    await poll(generation.id);
  } catch (sendError) {
    error.value = sendError.message;
  } finally {
    generating.value = false;
  }
};
</script>

<template>
  <PageHeader title="我的订单与服务" sub="查看属于当前账户的订单，并通过 AI 与坐席协同获得支持">
    <AppButton>帮助中心</AppButton>
  </PageHeader>
  <div class="customer-layout">
    <section class="panel customer-tickets">
      <h2>我的订单</h2>
      <button
        v-for="order in orders"
        :key="order.orderNo"
        :class="selectedOrder?.orderNo === order.orderNo ? 'customer-ticket selected' : 'customer-ticket'"
        @click="selectedOrder = order"
      >
        <strong>{{ order.orderNo }}</strong>
        <span>{{ order.status }}</span>
        <p>{{ currencyAmount(order.totalAmount, order.currency) }}</p>
        <small>下单时间：{{ formatDateTime(order.createdAt) }}</small>
      </button>
      <p v-if="!orders.length && !error" class="empty-state">正在加载订单…</p>
      <p v-if="error" class="warning">{{ error }}</p>
    </section>
    <section class="panel customer-detail">
      <div class="detail-head">
        <div>
          <span class="eyebrow">客服会话</span>
          <h2>{{ selectedOrder ? `订单 ${selectedOrder.orderNo} 的服务咨询` : '选择一个订单开始咨询' }}</h2>
          <small>消息采用独立生成任务，网络中断后可从最后事件继续读取。</small>
        </div>
        <span :class="generating ? 'status processing' : 'status success'">{{ generating ? 'AI 正在处理' : '账户已验证' }}</span>
      </div>
      <div class="conversation-body">
        <div v-if="!messages.length" class="customer-message">
          <strong>下一步</strong>
          <p>提交订单问题后，系统会检索租户知识库；证据不足、模型失败或高风险动作会自动转人工。</p>
        </div>
        <div
          v-for="(item, index) in messages"
          :key="index"
          :class="`message ${item.role === 'assistant' ? 'ai' : item.role === 'system' ? 'note' : 'customer'}`"
        >
          <span class="message-avatar"><Bot v-if="item.role === 'assistant'" :size="17" /><template v-else>{{ item.role === 'system' ? '内' : '客' }}</template></span>
          <div>
            <small>{{ item.role === 'assistant' ? 'SupportFlow AI' : item.role === 'system' ? '服务状态' : '我' }}</small>
            <p>{{ item.content }}</p>
          </div>
        </div>
      </div>
      <form class="composer" @submit.prevent="send">
        <textarea
          :value="message"
          :placeholder="selectedOrder ? '描述订单问题…' : '请先选择订单'"
          :disabled="!selectedOrder || generating"
          @input="message = $event.target.value"
        ></textarea>
        <div class="customer-actions"><AppButton primary :icon="Send">{{ generating ? '生成中…' : '发送消息' }}</AppButton></div>
      </form>
      <p class="safe-note"><ShieldCheck :size="15" />退款和补偿必须经过人工审批，系统不会在会话中直接执行资金操作。</p>
    </section>
  </div>
</template>
