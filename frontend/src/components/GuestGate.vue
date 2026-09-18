<script setup>
import {LockKeyhole} from '@lucide/vue';
import AppButton from './AppButton.vue';
import PageHeader from './PageHeader.vue';

defineEmits(['go-account']);
</script>

<template>
  <PageHeader title="登录后可用" sub="该功能区保存在你的工作区中，需要账户会话" />
  <section class="panel guest-gate">
    <div class="guest-gate-icon"><LockKeyhole :size="26" /></div>
    <h2>登录后解锁工单协同、知识库与审批</h2>
    <p>打开客户端即进入工作台；前往个人中心登录既有账户，或直接创建新的工作区。</p>
    <AppButton primary @click="$emit('go-account')">前往个人中心登录</AppButton>
  </section>
</template>
