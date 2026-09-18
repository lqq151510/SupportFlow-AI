<script setup>
import {ref} from 'vue';
import {AlertTriangle, ShieldCheck} from '@lucide/vue';
import {getSession, login, registerCustomer, registerTenant} from '../api.js';

const props = defineProps({
  backendStatus: {type: String, default: 'checking'},
});
const emit = defineEmits(['recheck-backend', 'signed-in']);

// 访客态的登录/注册面板：打开客户端直接进入工作台，认证动作全部收敛在个人中心。
const error = ref('');
const submitting = ref(false);
const mode = ref('login');
const tenantCode = ref(globalThis.localStorage?.getItem('supportflow.tenantCode') || '');

const submit = async event => {
  error.value = '';
  submitting.value = true;
  const values = new FormData(event.target);
  try {
    let submittedTenantCode = values.get('tenantCode');
    if (mode.value === 'customer-register') {
      await registerCustomer({tenantCode: submittedTenantCode, email: values.get('email'), displayName: values.get('displayName'), password: values.get('password')});
    }
    if (mode.value === 'tenant-register') {
      const registration = await registerTenant({email: values.get('email'), displayName: values.get('displayName'), password: values.get('password')});
      submittedTenantCode = registration.tenantCode;
    }
    const tokens = await login({tenantCode: submittedTenantCode, email: values.get('email'), password: values.get('password')});
    localStorage.setItem('supportflow.tenantCode', submittedTenantCode);
    tenantCode.value = submittedTenantCode;
    localStorage.setItem('supportflow.accessToken', tokens.accessToken);
    localStorage.setItem('supportflow.refreshToken', tokens.refreshToken);
    emit('signed-in', await getSession());
  } catch (loginError) {
    localStorage.removeItem('supportflow.accessToken');
    localStorage.removeItem('supportflow.refreshToken');
    error.value = loginError.message;
  } finally {
    submitting.value = false;
  }
};

const switchMode = nextMode => {
  mode.value = nextMode;
  error.value = '';
};
</script>

<template>
  <div class="account-center">
    <section class="panel auth-panel-card">
      <div class="brand"><span class="brand-mark">◉</span><span>SupportFlow AI</span></div>
      <div :class="`backend-status ${props.backendStatus}`" role="status">
        <span></span>
        <div>
          <strong>{{ props.backendStatus === 'connected' ? '本地服务已连接' : props.backendStatus === 'checking' ? '正在检测本地服务' : '本地服务未连接' }}</strong>
          <small>{{ props.backendStatus === 'disconnected' ? '请先启动 SupportFlow 后端，再重新检测。' : '后端地址：http://localhost:8080' }}</small>
        </div>
        <button v-if="props.backendStatus === 'disconnected'" type="button" @click="emit('recheck-backend')">重新检测</button>
      </div>
      <h1>{{ mode === 'tenant-register' ? '创建工作区管理员' : mode === 'customer-register' ? '创建消费者账户' : '登录服务工作台' }}</h1>
      <p>{{ mode === 'tenant-register' ? '首次使用只需填写姓名、邮箱和密码；系统会自动创建工作区并让你成为管理员。' : mode === 'customer-register' ? (tenantCode ? '将使用此 Mac 已保存的工作区注册，注册后会生成演示订单。' : '请先创建或切换到一个工作区，消费者注册会自动使用当前工作区。') : tenantCode ? '使用本机已保存的工作区登录；需要切换工作区时再输入代码。' : '使用租户代码、邮箱和密码进入消费者或坐席视图。' }}</p>
      <form @submit.prevent="submit">
        <template v-if="mode !== 'tenant-register'">
          <template v-if="tenantCode">
            <input name="tenantCode" type="hidden" :value="tenantCode" />
            <p class="safe-note">此 Mac 已保存当前工作区。<button type="button" class="text-link" @click="tenantCode = ''">切换工作区</button></p>
          </template>
          <label v-else>租户代码<input class="input field" name="tenantCode" required autocomplete="organization" placeholder="例如 my-store" /></label>
        </template>
        <label v-if="mode !== 'login'">显示名称<input class="input field" name="displayName" required autocomplete="name" /></label>
        <label>邮箱<input class="input field" name="email" type="email" required autocomplete="email" /></label>
        <label>密码<input class="input field" name="password" type="password" required minlength="12" :autocomplete="mode !== 'login' ? 'new-password' : 'current-password'" /></label>
        <p v-if="error" class="warning"><AlertTriangle :size="15" />{{ error }}</p>
        <button type="submit" class="btn primary" :disabled="props.backendStatus !== 'connected' || submitting">
          {{ submitting ? (mode === 'customer-register' ? '注册中…' : mode === 'tenant-register' ? '创建中…' : '登录中…') : (mode === 'customer-register' ? '注册并登录' : mode === 'tenant-register' ? '创建并登录' : '登录') }}
        </button>
      </form>
      <button v-if="mode !== 'login'" class="text-link" @click="switchMode('login')">已有账户？返回登录</button>
      <div v-else class="login-links">
        <button class="text-link" @click="switchMode('tenant-register')">首次使用？创建工作区</button>
        <button class="text-link" @click="switchMode('customer-register')">新用户？注册消费者账户</button>
      </div>
      <p class="safe-note"><ShieldCheck :size="15" />登录令牌和当前工作区标识只保存在此 Mac 的浏览器本地存储中；下次打开客户端会自动续登，直接进入工作台。</p>
    </section>
  </div>
</template>
