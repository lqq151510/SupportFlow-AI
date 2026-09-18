<script setup>
import {onMounted, ref} from 'vue';
import {Bot, Pencil, Plus, ShieldCheck, Sparkles, Wrench} from '@lucide/vue';
import {
  createModelConfig,
  getModelConfigs,
  probeModelConnection,
  setDefaultModelConfig,
  setKnowledgeDefaultModelConfig,
  updateModelConfig,
} from '../api.js';

const emit = defineEmits(['notice']);

const initialForm = {
  name: '',
  protocol: 'OPENAI_COMPATIBLE',
  baseUrl: '',
  modelName: '',
  apiKey: '',
  isDefault: true,
  isKnowledgeDefault: false,
};

const models = ref([]);
const form = ref({...initialForm});
const editingId = ref(null); // null、'new' 或具体 modelId
const busy = ref(false);
const error = ref('');

const notify = message => emit('notice', message);

const load = () => getModelConfigs().then(items => {models.value = items;}).catch(loadError => {error.value = loadError.message;});

onMounted(() => {
  load();
});

const update = event => {
  const {name, type, value, checked} = event.target;
  form.value = {...form.value, [name]: type === 'checkbox' ? checked : value};
};

const startCreate = () => {
  editingId.value = 'new';
  form.value = {...initialForm};
  error.value = '';
};

const startEdit = model => {
  editingId.value = model.id;
  form.value = {
    name: model.name,
    protocol: model.protocol,
    baseUrl: model.baseUrl,
    modelName: model.modelName,
    apiKey: '',
    isDefault: Boolean(model.isDefault),
    isKnowledgeDefault: Boolean(model.isKnowledgeDefault),
  };
  error.value = '';
};

const probe = async () => {
  if (!form.value.baseUrl) {
    error.value = '测试连接前请填写 Base URL。';
    return;
  }
  busy.value = true;
  error.value = '';
  try {
    const result = await probeModelConnection(form.value);
    notify(result.reachable ? `连接成功：${result.message}` : `连接响应：${result.message}`);
  } catch (actionError) {
    error.value = actionError.message;
  } finally {
    busy.value = false;
  }
};

const save = async () => {
  busy.value = true;
  error.value = '';
  try {
    if (editingId.value === 'new' || !editingId.value) {
      if (!form.value.apiKey) {
        error.value = '新增模型必须填写 API Key。';
        busy.value = false;
        return;
      }
      await createModelConfig(form.value);
      notify('模型配置已加密保存。');
    } else {
      await updateModelConfig(editingId.value, form.value);
      notify('模型配置已就地更新。');
    }
    editingId.value = null;
    form.value = {...initialForm};
    await load();
  } catch (actionError) {
    error.value = actionError.message;
  } finally {
    busy.value = false;
  }
};

const makeDefault = async model => {
  if (model.isDefault || busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await setDefaultModelConfig(model.id);
    await load();
    notify(`已切换默认客服推理模型：${model.name}`);
  } catch (actionError) {
    error.value = actionError.message;
  } finally {
    busy.value = false;
  }
};

const makeKnowledgeDefault = async model => {
  if (model.isKnowledgeDefault || busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await setKnowledgeDefaultModelConfig(model.id);
    await load();
    notify(`已切换知识库自动整理模型：${model.name}`);
  } catch (actionError) {
    error.value = actionError.message;
  } finally {
    busy.value = false;
  }
};
</script>

<template>
  <div class="page-header">
    <div>
      <h1>模型配置与场景路由</h1>
      <p>管理聊天推理、知识库整理协议、端点和加密凭据（支持 DeepSeek / OpenAI / Claude）</p>
    </div>
    <div class="header-actions">
      <button class="btn primary" @click="startCreate"><Plus :size="16" />新增模型</button>
    </div>
  </div>
  <p v-if="error" class="warning">{{ error }}</p>
  <section class="settings-status-strip" aria-label="模型配置状态">
    <div><span>已接入模型</span><strong>{{ models.length }}</strong><small>{{ models.length ? '可用于当前工作区' : '尚未接入云端模型' }}</small></div>
    <div><span>客服推理</span><strong>{{ models.find(model => model.isDefault)?.name || '未设置' }}</strong><small>决定 AI 客服会话的默认模型</small></div>
    <div><span>知识库整理</span><strong>{{ models.find(model => model.isKnowledgeDefault)?.name || '未设置' }}</strong><small>决定文档摘要与标签整理模型</small></div>
    <button class="btn" @click="startCreate"><Plus :size="15" />接入模型</button>
  </section>
  <div class="settings-grid">
    <section class="panel model-list">
      <h2>已配置模型</h2>
      <div
        v-for="model in models"
        :key="model.id"
        :class="`model-row ${model.isDefault ? 'selected ' : ''}${model.isKnowledgeDefault ? 'kb-selected' : ''}`"
      >
        <span class="model-icon"><Bot :size="17" /></span>
        <div>
          <strong>{{ model.name }} · {{ model.protocol }}</strong>
          <small>{{ model.modelName }} · {{ model.baseUrl }}</small>
          <div class="model-inline-tags">
            <span v-if="model.isDefault" class="badge badge-chat"><Sparkles :size="11" /> 默认推理</span>
            <span v-if="model.isKnowledgeDefault" class="badge badge-kb"><Wrench :size="11" /> 知识整理</span>
          </div>
        </div>
        <div class="model-row-actions">
          <button class="btn sm" @click="startEdit(model)"><Pencil :size="13" /> 编辑</button>
          <button v-if="!model.isDefault" class="btn sm" :disabled="busy" @click="makeDefault(model)">设为默认</button>
          <button v-if="!model.isKnowledgeDefault" class="btn sm" :disabled="busy" @click="makeKnowledgeDefault(model)">设为知识整理</button>
        </div>
      </div>
      <p v-if="!models.length" class="empty-state padded">未接入云端模型。请添加并设为默认的云端模型配置（如 DeepSeek / OpenAI）后再开始 AI 会话。</p>
    </section>

    <section class="panel config-form">
      <div class="panel-head">
        <h2>{{ editingId && editingId !== 'new' ? '就地编辑模型配置' : '新云端模型接入' }}</h2>
        <span class="status success">AES-GCM 加密</span>
      </div>
      <form class="admin-form" @submit.prevent="save">
        <label>配置名称
          <input class="input field-input" name="name" :value="form.name" @input="update" required maxlength="128" placeholder="例如：DeepSeek 生产主力" />
        </label>
        <label>协议类型
          <select class="input field-input" name="protocol" :value="form.protocol" @change="update">
            <option value="OPENAI_COMPATIBLE">OPENAI_COMPATIBLE (DeepSeek / OpenAI)</option>
            <option value="ANTHROPIC_MESSAGES">ANTHROPIC_MESSAGES (Claude Messages)</option>
          </select>
        </label>
        <label>Base URL
          <input class="input field-input" name="baseUrl" :value="form.baseUrl" @input="update" required type="url" placeholder="https://api.deepseek.com/v1" />
        </label>
        <label>模型名称
          <input class="input field-input" name="modelName" :value="form.modelName" @input="update" required placeholder="deepseek-chat / gpt-4o" />
        </label>
        <label>API Key
          <input
            class="input field-input"
            name="apiKey"
            :value="form.apiKey"
            @input="update"
            type="password"
            autocomplete="off"
            :placeholder="editingId && editingId !== 'new' ? '留空则保留原加密密钥' : '仅在保存时提交'"
          />
        </label>
        <label class="check">
          <input name="isDefault" type="checkbox" :checked="form.isDefault" @change="update" />
          设为当前租户默认客服推理模型
        </label>
        <label class="check">
          <input name="isKnowledgeDefault" type="checkbox" :checked="form.isKnowledgeDefault" @change="update" />
          设为知识库自动整理模型 (DeepSeek / OpenAI)
        </label>
        <div class="form-actions">
          <button v-if="editingId" class="btn" type="button" @click="editingId = null">取消</button>
          <button class="btn" type="button" :disabled="busy" @click="probe">测试连接</button>
          <button class="btn primary" :disabled="busy">{{ busy ? '保存中…' : '保存配置' }}</button>
        </div>
      </form>
      <p class="safe-note"><ShieldCheck :size="15" />API Key 采用 AES-GCM 加密，列表接口永不返回明文；网关按请求读取当前默认配置，切换后无需等待客户端缓存失效。</p>
    </section>
  </div>
</template>
