<script setup>
import {computed, ref, watch} from 'vue';
import {
  Activity,
  Bot,
  Coins,
  Copy,
  DollarSign,
  KeyRound,
  LoaderCircle,
  LogOut,
  Pencil,
  Plus,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  UserRound,
  Wrench,
  X,
  Zap,
} from '@lucide/vue';
import {
  changePassword,
  createModelConfig,
  getModelConfigs,
  getModelUsageOverview,
  getMyProfile,
  getRecentModelUsages,
  probeModelConnection,
  revokeSession,
  setDefaultModelConfig,
  setKnowledgeDefaultModelConfig,
  updateModelConfig,
  updateMyProfile,
} from '../api.js';
import {formatJoinedAt, formatTime, initials, roleLabel, scenarioLabel} from '../lib/format.js';
import AuthPanel from './AuthPanel.vue';

const props = defineProps({
  session: {type: Object, default: null},
  backendStatus: {type: String, default: 'checking'},
});
const emit = defineEmits(['notice', 'profile-change', 'open-model-settings', 'recheck-backend', 'signed-in']);

const notify = message => emit('notice', message);

const profile = ref(null);
const models = ref([]);
const usageStats = ref(null);
const recentRecords = ref([]);
const loading = ref(Boolean(props.session));
const refreshing = ref(false);
const error = ref('');

// 个人资料编辑
const editing = ref(false);
const displayName = ref('');
const saving = ref(false);

// 修改密码
const passwordOpen = ref(false);
const passwords = ref({currentPassword: '', newPassword: '', confirmPassword: ''});
const passwordSaving = ref(false);

// 就地模型编辑
const editingModelId = ref(null); // 'new' 或 modelId
const modelForm = ref({
  name: '',
  protocol: 'OPENAI_COMPATIBLE',
  baseUrl: '',
  modelName: '',
  apiKey: '',
  isDefault: false,
  isKnowledgeDefault: false,
});
const modelSaving = ref(false);

const isAdmin = computed(() => props.session?.role === 'TENANT_ADMIN');

const loadData = async (silent = false) => {
  if (!props.session) return;
  if (!silent) loading.value = true;
  else refreshing.value = true;
  error.value = '';
  try {
    const [loadedProfile, loadedModels, loadedStats, loadedRecent] = await Promise.all([
      getMyProfile(),
      isAdmin.value ? getModelConfigs() : Promise.resolve([]),
      isAdmin.value ? getModelUsageOverview().catch(() => null) : Promise.resolve(null),
      isAdmin.value ? getRecentModelUsages(15).catch(() => []) : Promise.resolve([]),
    ]);
    profile.value = loadedProfile;
    displayName.value = loadedProfile.displayName;
    models.value = loadedModels;
    usageStats.value = loadedStats;
    recentRecords.value = loadedRecent || [];
    emit('profile-change', loadedProfile);
  } catch (loadError) {
    error.value = loadError.message;
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
};

watch([isAdmin, () => props.session], () => {
  // 访客态不发起任何需要会话的请求；登录状态变化时重新加载。
  if (!props.session) {
    profile.value = null;
    models.value = [];
    usageStats.value = null;
    recentRecords.value = [];
    error.value = '';
    loading.value = false;
    return;
  }
  loadData();
}, {immediate: true});

const handleLogout = () => {
  revokeSession(localStorage.getItem('supportflow.refreshToken'));
  localStorage.removeItem('supportflow.accessToken');
  localStorage.removeItem('supportflow.refreshToken');
  notify('已退出登录。');
  emit('signed-in', null);
};

const saveProfile = async () => {
  if (!displayName.value.trim() || saving.value) return;
  saving.value = true;
  try {
    const updated = await updateMyProfile({displayName: displayName.value.trim()});
    profile.value = updated;
    displayName.value = updated.displayName;
    emit('profile-change', updated);
    editing.value = false;
    notify('个人资料已保存。');
  } catch (saveError) {
    error.value = saveError.message;
  } finally {
    saving.value = false;
  }
};

const savePassword = async () => {
  if (passwordSaving.value) return;
  if (passwords.value.newPassword !== passwords.value.confirmPassword) {
    error.value = '两次输入的新密码不一致。';
    return;
  }
  passwordSaving.value = true;
  try {
    await changePassword(passwords.value);
    passwords.value = {currentPassword: '', newPassword: '', confirmPassword: ''};
    passwordOpen.value = false;
    notify('密码已更新；其他已登录设备的会话已失效。');
  } catch (saveError) {
    error.value = saveError.message;
  } finally {
    passwordSaving.value = false;
  }
};

const copyWorkspaceCode = async () => {
  try {
    await navigator.clipboard.writeText(profile.value.tenantCode);
    notify('工作区代码已复制。');
  } catch {
    error.value = '无法访问系统剪贴板，请手动复制工作区代码。';
  }
};

const startEditModel = model => {
  if (model) {
    editingModelId.value = model.id;
    modelForm.value = {
      name: model.name,
      protocol: model.protocol,
      baseUrl: model.baseUrl,
      modelName: model.modelName,
      apiKey: '', // 留空表示不修改已有 Key
      isDefault: Boolean(model.isDefault),
      isKnowledgeDefault: Boolean(model.isKnowledgeDefault),
    };
  } else {
    editingModelId.value = 'new';
    modelForm.value = {
      name: '',
      protocol: 'OPENAI_COMPATIBLE',
      baseUrl: 'https://api.deepseek.com/v1',
      modelName: 'deepseek-chat',
      apiKey: '',
      isDefault: models.value.length === 0,
      isKnowledgeDefault: models.value.length === 0,
    };
  }
};

const cancelEditModel = () => {
  editingModelId.value = null;
  error.value = '';
};

const setModelField = (field, value) => {
  modelForm.value = {...modelForm.value, [field]: value};
};

const probeCurrentForm = async () => {
  if (!modelForm.value.baseUrl) {
    error.value = '测试连接前请填写 Base URL。';
    return;
  }
  modelSaving.value = true;
  error.value = '';
  try {
    const result = await probeModelConnection({baseUrl: modelForm.value.baseUrl, apiKey: modelForm.value.apiKey || 'test'});
    notify(result.reachable ? `连接探测成功：${result.message}` : `探测响应：${result.message}`);
  } catch (err) {
    error.value = err.message;
  } finally {
    modelSaving.value = false;
  }
};

const saveModelForm = async () => {
  modelSaving.value = true;
  error.value = '';
  try {
    if (editingModelId.value === 'new') {
      if (!modelForm.value.apiKey) {
        error.value = '新建模型源必须填写 API Key。';
        modelSaving.value = false;
        return;
      }
      await createModelConfig(modelForm.value);
      notify('新模型源已加密接入并保存。');
    } else {
      await updateModelConfig(editingModelId.value, modelForm.value);
      notify('模型配置已原地更新并加密保存。');
    }
    editingModelId.value = null;
    await loadData(true);
  } catch (err) {
    error.value = err.message;
  } finally {
    modelSaving.value = false;
  }
};

const handleSetChatDefault = async modelId => {
  modelSaving.value = true;
  try {
    await setDefaultModelConfig(modelId);
    await loadData(true);
    notify('已切换当前租户默认推理/客服模型。');
  } catch (err) {
    error.value = err.message;
  } finally {
    modelSaving.value = false;
  }
};

const handleSetKnowledgeDefault = async modelId => {
  modelSaving.value = true;
  try {
    await setKnowledgeDefaultModelConfig(modelId);
    await loadData(true);
    notify('已切换当前租户知识库自动整理模型。');
  } catch (err) {
    error.value = err.message;
  } finally {
    modelSaving.value = false;
  }
};

const totalCalls = computed(() => usageStats.value?.totalCalls || 0);
const totalTokens = computed(() => usageStats.value?.totalTokens || 0);
const totalInputTokens = computed(() => usageStats.value?.totalInputTokens || 0);
const totalOutputTokens = computed(() => usageStats.value?.totalOutputTokens || 0);
const avgLatency = computed(() => usageStats.value?.averageLatencyMs || 0);
const costCny = computed(() => (usageStats.value?.totalEstimatedCostCny ? Number(usageStats.value.totalEstimatedCostCny).toFixed(4) : '0.0000'));
const costUsd = computed(() => (usageStats.value?.totalEstimatedCostUsd ? Number(usageStats.value.totalEstimatedCostUsd).toFixed(4) : '0.0000'));
const scenarioEntries = computed(() => Object.entries(usageStats.value?.scenarioCalls || {}));
const modelTokenEntries = computed(() => Object.entries(usageStats.value?.modelTokens || {}));
const scenarioPercent = count => (totalCalls.value > 0 ? Math.round((count / totalCalls.value) * 100) : 0);
const modelCost = model => (usageStats.value?.modelCostCny?.[model] ? Number(usageStats.value.modelCostCny[model]).toFixed(4) : '0.0000');
</script>

<template>
  <AuthPanel
    v-if="!props.session"
    :backend-status="props.backendStatus"
    @recheck-backend="emit('recheck-backend')"
    @signed-in="emit('signed-in', $event)"
  />
  <div v-else-if="loading" class="account-loading">
    <LoaderCircle :size="20" class="spin" /><span>正在读取你的本地账户与数据看板…</span>
  </div>
  <section v-else-if="!profile" class="account-error panel">
    <h1>个人中心暂不可用</h1>
    <p>{{ error || '无法读取当前账户资料。' }}</p>
    <button class="btn" @click="loadData()">重新加载</button>
  </section>
  <div v-else class="account-center">
    <!-- 头部 Hero -->
    <section class="account-hero">
      <div class="account-hero-glow"></div>
      <div class="account-avatar large">{{ initials(profile.displayName) }}</div>
      <div class="account-identity">
        <div class="eyebrow-row">
          <span class="eyebrow">PERSONAL CONSOLE</span>
          <span class="shortcut-tag"><kbd>⌘</kbd> <kbd>,</kbd> 快捷唤出/切回</span>
        </div>
        <h1>{{ profile.displayName }}</h1>
        <p>{{ roleLabel[profile.role] || profile.role }} · {{ profile.tenantName }}</p>
      </div>
      <div class="account-security-badge">
        <ShieldCheck :size="18" /><span>多租户加密隔离</span>
        <button class="icon-btn-ghost" title="刷新数据" @click="loadData(true)">
          <RefreshCcw :size="16" :class="refreshing ? 'spin' : ''" />
        </button>
      </div>
    </section>

    <p v-if="error" class="warning account-warning"><X :size="15" />{{ error }}</p>

    <!-- 数据看板：全链路真实 Token 归集与费用核算 -->
    <section v-if="isAdmin" class="panel account-usage-dashboard">
      <div class="panel-head">
        <div class="head-title">
          <Coins :size="20" class="icon-gold" />
          <div>
            <h2>真实 API 费用与 Token 归集看板</h2>
            <p>全链路自动记录会话交互、知识库整理与模型测试的真实消耗与经济成本</p>
          </div>
        </div>
        <div class="dashboard-badges">
          <span class="status success"><Activity :size="14" /> 实时入库</span>
        </div>
      </div>

      <div class="usage-stats-grid">
        <div class="stat-card cost-highlight">
          <span class="stat-label">预估累计调用成本 (CNY)</span>
          <strong class="stat-value cny-amount">¥ {{ costCny }}</strong>
          <small class="stat-sub">折合美元 ≈ ${{ costUsd }} (汇率 7.2)</small>
        </div>

        <div class="stat-card">
          <span class="stat-label">累计消耗总 Token</span>
          <strong class="stat-value">{{ totalTokens.toLocaleString() }}</strong>
          <small class="stat-sub">输入 {{ totalInputTokens.toLocaleString() }} · 输出 {{ totalOutputTokens.toLocaleString() }}</small>
        </div>

        <div class="stat-card">
          <span class="stat-label">全场景模型调用次数</span>
          <strong class="stat-value">{{ totalCalls.toLocaleString() }} 次</strong>
          <small class="stat-sub">平均响应耗时 {{ avgLatency }} ms</small>
        </div>
      </div>

      <!-- 场景与模型分布 -->
      <div class="usage-breakdown-row">
        <div class="breakdown-box">
          <span class="box-title"><Zap :size="15" /> 场景分布</span>
          <div class="scenario-bars">
            <template v-if="scenarioEntries.length > 0">
              <div v-for="[sc, count] in scenarioEntries" :key="sc" class="bar-item">
                <div class="bar-info">
                  <span>{{ scenarioLabel[sc] || sc }}</span>
                  <b>{{ count }} 次 ({{ scenarioPercent(count) }}%)</b>
                </div>
                <div class="progress mini"><span :style="{width: `${scenarioPercent(count)}%`}"></span></div>
              </div>
            </template>
            <p v-else class="empty-sub">暂无多场景调用记录，进行客服会话或知识库整理后将实时更新。</p>
          </div>
        </div>

        <div class="breakdown-box">
          <span class="box-title"><DollarSign :size="15" /> 模型消费与 Token 分布</span>
          <div class="model-breakdown-list">
            <template v-if="modelTokenEntries.length > 0">
              <div v-for="[model, tCount] in modelTokenEntries" :key="model" class="model-cost-row">
                <div class="model-name-col">
                  <strong>{{ model }}</strong>
                  <small>{{ tCount.toLocaleString() }} Tokens</small>
                </div>
                <span class="model-cost-badge">¥ {{ modelCost(model) }}</span>
              </div>
            </template>
            <p v-else class="empty-sub">支持 DeepSeek / OpenAI 等模型定价，接入后自动核算单次开销。</p>
          </div>
        </div>
      </div>
    </section>

    <div class="account-grid">
      <!-- 账户资料 -->
      <section class="panel account-card account-profile-card">
        <div class="panel-head">
          <div><span class="eyebrow">ACCOUNT</span><h2>账户资料</h2></div>
          <button v-if="!editing" class="btn" @click="editing = true"><Pencil :size="15" />编辑资料</button>
        </div>
        <form v-if="editing" class="account-form" @submit.prevent="saveProfile">
          <label>显示名称<input class="input field-input" v-model="displayName" maxlength="128" required autocomplete="name" /></label>
          <div class="form-actions">
            <button class="btn" type="button" @click="editing = false; displayName = profile.displayName">取消</button>
            <button class="btn primary" :disabled="saving">{{ saving ? '保存中…' : '保存资料' }}</button>
          </div>
        </form>
        <dl v-else class="account-details">
          <div><dt>邮箱</dt><dd>{{ profile.email }}</dd></div>
          <div><dt>角色</dt><dd>{{ roleLabel[profile.role] || profile.role }}</dd></div>
          <div><dt>加入工作区</dt><dd>{{ formatJoinedAt(profile.joinedAt) }}</dd></div>
        </dl>
      </section>

      <!-- 当前工作区 -->
      <section class="panel account-card workspace-card">
        <div class="panel-head"><div><span class="eyebrow">WORKSPACE</span><h2>当前工作区</h2></div><UserRound :size="19" /></div>
        <strong>{{ profile.tenantName }}</strong>
        <p>当前账号在工作区内角色为{{ roleLabel[profile.role] || profile.role }}。租户与模型数据由 JWT 上下文严格隔离。</p>
        <div class="workspace-code">
          <span>租户代码</span><code>{{ profile.tenantCode }}</code>
          <button class="icon-btn" aria-label="复制工作区代码" @click="copyWorkspaceCode"><Copy :size="16" /></button>
        </div>
        <button v-if="isAdmin" class="btn model-settings-link" @click="emit('open-model-settings')">前往设置管理模型与通知</button>
      </section>

      <!-- 模型 API 接入与就地编辑卡片 -->
      <section class="panel account-card model-access-card full-width">
        <div class="panel-head">
          <div><span class="eyebrow">AI MODEL ROUTING</span><h2>模型 API 接入与场景路由</h2></div>
          <button v-if="isAdmin && !editingModelId" class="btn primary" @click="startEditModel(null)">
            <Plus :size="16" />接入新模型 (DeepSeek / OpenAI)
          </button>
        </div>

        <template v-if="isAdmin">
          <form v-if="editingModelId" class="inline-model-editor panel" @submit.prevent="saveModelForm">
            <div class="editor-head">
              <h3>{{ editingModelId === 'new' ? '接入新云端模型源' : '就地编辑模型配置' }}</h3>
              <span class="safe-tag"><ShieldCheck :size="14" /> AES-GCM 密文存储</span>
            </div>
            <div class="editor-grid">
              <label>配置名称
                <input class="input field-input" :value="modelForm.name" required placeholder="例如：DeepSeek 生产主力 / GPT-4o 整理" @input="setModelField('name', $event.target.value)" />
              </label>
              <label>协议类型
                <select class="input field-input" :value="modelForm.protocol" @change="setModelField('protocol', $event.target.value)">
                  <option value="OPENAI_COMPATIBLE">OPENAI_COMPATIBLE (DeepSeek / OpenAI / 本地兼容)</option>
                  <option value="ANTHROPIC_MESSAGES">ANTHROPIC_MESSAGES (Claude Messages)</option>
                </select>
              </label>
              <label>Base URL
                <input class="input field-input" type="url" :value="modelForm.baseUrl" required placeholder="https://api.deepseek.com/v1" @input="setModelField('baseUrl', $event.target.value)" />
              </label>
              <label>模型名称 (Model Identifier)
                <input class="input field-input" :value="modelForm.modelName" required placeholder="deepseek-chat / gpt-4o" @input="setModelField('modelName', $event.target.value)" />
              </label>
              <label class="full-col">API Key
                <input
                  class="input field-input"
                  type="password"
                  :value="modelForm.apiKey"
                  :placeholder="editingModelId === 'new' ? '输入模型 API Key' : '留空则保留原有加密密钥'"
                  autocomplete="off"
                  @input="setModelField('apiKey', $event.target.value)"
                />
              </label>
            </div>
            <div class="checkbox-row">
              <label class="check">
                <input type="checkbox" :checked="modelForm.isDefault" @change="setModelField('isDefault', $event.target.checked)" />
                设为默认客服推理模型 (Chat Default)
              </label>
              <label class="check">
                <input type="checkbox" :checked="modelForm.isKnowledgeDefault" @change="setModelField('isKnowledgeDefault', $event.target.checked)" />
                设为知识库自动整理模型 (Knowledge Default)
              </label>
            </div>
            <div class="editor-actions">
              <button class="btn" type="button" @click="cancelEditModel">取消</button>
              <button class="btn" type="button" :disabled="modelSaving" @click="probeCurrentForm">测试端点连接</button>
              <button class="btn primary" :disabled="modelSaving">{{ modelSaving ? '保存中…' : '保存模型配置' }}</button>
            </div>
          </form>

          <div class="model-cards-list">
            <div
              v-for="model in models"
              :key="model.id"
              :class="`model-item-card ${model.isDefault ? 'active-chat ' : ''}${model.isKnowledgeDefault ? 'active-kb' : ''}`"
            >
              <div class="model-item-header">
                <div class="model-title-wrap">
                  <span class="model-avatar"><Bot :size="18" /></span>
                  <div>
                    <strong>{{ model.name }}</strong>
                    <small>{{ model.modelName }} · {{ model.protocol }}</small>
                  </div>
                </div>
                <div class="model-tags">
                  <span v-if="model.isDefault" class="badge badge-chat"><Sparkles :size="12" /> 默认客服推理</span>
                  <span v-if="model.isKnowledgeDefault" class="badge badge-kb"><Wrench :size="12" /> 知识库整理模型</span>
                </div>
              </div>

              <div class="model-url-line">
                <code>{{ model.baseUrl }}</code>
              </div>

              <div class="model-card-actions">
                <button class="btn sm" @click="startEditModel(model)"><Pencil :size="13" />就地编辑</button>
                <button v-if="!model.isDefault" class="btn sm" :disabled="modelSaving" @click="handleSetChatDefault(model.id)">设为默认推理</button>
                <button v-if="!model.isKnowledgeDefault" class="btn sm" :disabled="modelSaving" @click="handleSetKnowledgeDefault(model.id)">设为知识整理</button>
              </div>
            </div>

            <div v-if="!models.length && !editingModelId" class="model-empty-box">
              <Bot :size="32" />
              <strong>暂未接入任何云端模型 API</strong>
              <p>点击上方“接入新模型”，即可接入 DeepSeek、OpenAI 或 Claude 等端点，系统将自动启用智能问答与知识库智能整理。</p>
            </div>
          </div>
        </template>
        <div v-else class="model-empty-box">
          <Bot :size="28" />
          <strong>模型由工作区管理员统一配置</strong>
          <p>当前账号可体验已启用的 AI 客服与知识库整理能力。</p>
        </div>
      </section>

      <!-- 真实调用流水记录表格 -->
      <section v-if="isAdmin" class="panel account-card recent-usages-card full-width">
        <div class="panel-head">
          <div>
            <span class="eyebrow">AUDIT & TRACE</span>
            <h2>最近模型调用流水 (Real-time Usage Log)</h2>
          </div>
          <button class="btn sm" @click="loadData(true)"><RefreshCcw :size="14" /> 刷新流水</button>
        </div>
        <div class="table-responsive">
          <table class="usage-table">
            <thead>
              <tr>
                <th>调用时间</th>
                <th>业务场景</th>
                <th>模型名称</th>
                <th>输入 Tokens</th>
                <th>输出 Tokens</th>
                <th>总 Tokens</th>
                <th>耗时</th>
                <th>预估费用</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in recentRecords" :key="record.id">
                <td><small>{{ formatTime(record.createdAt) }}</small></td>
                <td><span class="badge-scenario">{{ scenarioLabel[record.scenario] || record.scenario }}</span></td>
                <td><strong>{{ record.modelName }}</strong></td>
                <td>{{ record.inputTokens.toLocaleString() }}</td>
                <td>{{ record.outputTokens.toLocaleString() }}</td>
                <td><b>{{ record.totalTokens.toLocaleString() }}</b></td>
                <td>{{ record.latencyMs }} ms</td>
                <td class="cost-cell">¥ {{ Number(record.estimatedCostCny || 0).toFixed(5) }}</td>
              </tr>
              <tr v-if="!recentRecords.length">
                <td colspan="8" class="empty-cell">当前还没有调用记录，发起客服对话或整理知识库后将在此实时展示。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 账户安全 -->
      <section class="panel account-card account-security-card full-width">
        <div class="panel-head"><div><span class="eyebrow">SECURITY</span><h2>账户安全</h2></div><KeyRound :size="19" /></div>
        <p>修改密码后，当前工作区下的刷新令牌会被立即撤销；其他已登录设备的会话将自动失效。退出登录会同步撤销本机的刷新令牌。</p>
        <div class="form-actions" style="justify-content: flex-start; margin-top: 0">
          <button class="btn" @click="passwordOpen = !passwordOpen; error = ''">{{ passwordOpen ? '收起修改密码' : '修改密码' }}</button>
          <button class="btn" @click="handleLogout"><LogOut :size="15" />退出登录</button>
        </div>
        <form v-if="passwordOpen" class="account-form password-form" @submit.prevent="savePassword">
          <label>当前密码<input class="input field-input" type="password" v-model="passwords.currentPassword" required autocomplete="current-password" /></label>
          <label>新密码<input class="input field-input" type="password" minlength="12" v-model="passwords.newPassword" required autocomplete="new-password" /></label>
          <label>确认新密码<input class="input field-input" type="password" minlength="12" v-model="passwords.confirmPassword" required autocomplete="new-password" /></label>
          <div class="form-actions"><button class="btn primary" :disabled="passwordSaving">{{ passwordSaving ? '更新中…' : '确认更新密码' }}</button></div>
        </form>
      </section>
    </div>
  </div>
</template>
