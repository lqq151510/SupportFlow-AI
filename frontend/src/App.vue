<script setup>
import {onMounted, ref} from 'vue';
import {getSession, refreshSession} from './api.js';
import Workspace from './Workspace.vue';

// undefined = 会话探测中，null = 访客，对象 = 已登录。
const session = ref(undefined);

onMounted(async () => {
  // 启动即进工作台：有有效会话直接进入；会话过期时用 refresh token 静默续登；
  // 两者都失败才进入访客态（仍停留在工作台，登录入口在个人中心）。
  try {
    session.value = await getSession();
    return;
  } catch {}
  const refreshToken = localStorage.getItem('supportflow.refreshToken');
  if (refreshToken) {
    try {
      const tokens = await refreshSession(refreshToken);
      localStorage.setItem('supportflow.accessToken', tokens.accessToken);
      localStorage.setItem('supportflow.refreshToken', tokens.refreshToken);
      session.value = await getSession();
      return;
    } catch {}
  }
  localStorage.removeItem('supportflow.accessToken');
  localStorage.removeItem('supportflow.refreshToken');
  session.value = null;
});
</script>

<template>
  <div v-if="session === undefined" class="login-shell">
    <div class="panel login-panel">
      <div class="brand"><span class="brand-mark">◉</span><span>SupportFlow AI</span></div>
      <p class="safe-note">正在进入工作台…</p>
    </div>
  </div>
  <Workspace v-else :session="session" @signed-in="session = $event" />
</template>
