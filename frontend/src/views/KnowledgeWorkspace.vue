<script setup>
import {onMounted, ref, watch} from 'vue';
import {BookOpen, FileText, LoaderCircle, Plus, Sparkles, Tag, Upload, X} from '@lucide/vue';
import {
  createKnowledgeBase,
  getKnowledgeBases,
  getKnowledgeDocuments,
  organizeKnowledgeDocument,
  uploadKnowledgeDocument,
} from '../api.js';

const emit = defineEmits(['notice']);

const statusLabel = status => ({UPLOADED: '已上传', PARSING: '解析中', CHUNKING: '切片中', EMBEDDING: '向量化中', INDEXED: '已索引', FAILED: '失败'})[status] || status;
const statusClass = status => (status === 'INDEXED' ? 'success' : status === 'FAILED' ? 'danger' : 'processing');

const bases = ref([]);
const selectedBase = ref(null);
const documents = ref([]);
const busy = ref(false);
const organizingDocId = ref(null);
const organizeResult = ref(null);
const error = ref('');
const fileInput = ref(null);

const notify = message => emit('notice', message);

const loadBases = async preferredId => {
  const items = await getKnowledgeBases();
  bases.value = items;
  selectedBase.value = items.find(item => item.id === (preferredId || selectedBase.value?.id)) || items[0] || null;
};

onMounted(() => {
  loadBases().catch(loadError => {error.value = loadError.message;});
});

watch(() => selectedBase.value?.id, () => {
  if (!selectedBase.value) {
    documents.value = [];
    return;
  }
  error.value = '';
  getKnowledgeDocuments(selectedBase.value.id).then(items => {documents.value = items;}).catch(loadError => {error.value = loadError.message;});
});

const createBase = async event => {
  const form = event.target;
  busy.value = true;
  error.value = '';
  try {
    const values = new FormData(form);
    const created = await createKnowledgeBase({name: values.get('name'), description: values.get('description')});
    form.reset();
    await loadBases(created.id);
    notify('知识库已创建。');
  } catch (actionError) {
    error.value = actionError.message;
  } finally {
    busy.value = false;
  }
};

const upload = async event => {
  const file = event.target.files?.[0];
  if (!file || !selectedBase.value) return;
  busy.value = true;
  error.value = '';
  try {
    await uploadKnowledgeDocument(selectedBase.value.id, file);
    documents.value = await getKnowledgeDocuments(selectedBase.value.id);
    notify(`${file.name} 已上传并进入摄取流程。`);
  } catch (actionError) {
    error.value = actionError.message;
  } finally {
    event.target.value = '';
    busy.value = false;
  }
};

const handleOrganize = async document => {
  if (!selectedBase.value || busy.value || organizingDocId.value) return;
  organizingDocId.value = document.id;
  error.value = '';
  try {
    const result = await organizeKnowledgeDocument(selectedBase.value.id, document.id);
    organizeResult.value = result;
    notify(`「${document.fileName}」整理预览已生成（处理方式：${result.modelUsed}）。结果基于当前文档切片，本次未写回文档元数据。`);
  } catch (err) {
    error.value = err.message;
  } finally {
    organizingDocId.value = null;
  }
};
</script>

<template>
  <div class="page-header">
    <div>
      <h1>知识库管理</h1>
      <p>按当前租户管理文档摄取、切片、向量索引与多模型智能整理（支持 DeepSeek / OpenAI）</p>
    </div>
    <div class="header-actions">
      <input ref="fileInput" class="visually-hidden" type="file" accept=".pdf,.doc,.docx,.md,.txt" @change="upload" />
      <button class="btn primary" :disabled="!selectedBase || busy" @click="fileInput?.click()">
        <Upload :size="16" />上传文档
      </button>
    </div>
  </div>
  <p v-if="error" class="warning">{{ error }}</p>

  <section v-if="organizeResult" class="panel organize-result-panel">
    <div class="panel-head">
      <div class="organize-title">
        <Sparkles :size="18" class="icon-sparkle" />
        <h3>文档整理预览 · {{ organizeResult.fileName }}</h3>
      </div>
      <button class="icon-btn" @click="organizeResult = null"><X :size="16" /></button>
    </div>
    <div class="organize-meta">
      <span>处理方式：<strong>{{ organizeResult.modelUsed }}</strong></span>
      <span>模型 Token：<b>{{ organizeResult.totalTokens > 0 ? organizeResult.totalTokens : '未调用模型' }}</b></span>
      <span>处理耗时：{{ organizeResult.latencyMs }} ms</span>
    </div>
    <div class="organize-body">
      <div class="organize-summary">
        <strong>【核心摘要】</strong>
        <p>{{ organizeResult.summary }}</p>
      </div>
      <div class="organize-tags">
        <strong>【智能标签】</strong>
        <div class="tags-wrap">
          <span v-for="(tag, idx) in organizeResult.tags || []" :key="idx" class="tag-chip"><Tag :size="12" />{{ tag }}</span>
        </div>
      </div>
    </div>
  </section>

  <div class="settings-grid">
    <section class="panel model-list">
      <h2>知识库</h2>
      <button
        v-for="item in bases"
        :key="item.id"
        :class="selectedBase?.id === item.id ? 'model-row model-row-button selected' : 'model-row model-row-button'"
        @click="selectedBase = item"
      >
        <span class="model-icon"><BookOpen :size="17" /></span>
        <div>
          <strong>{{ item.name }}</strong>
          <small>{{ item.description || '暂无描述' }}</small>
        </div>
        <span class="status success">{{ item.status }}</span>
      </button>
      <p v-if="!bases.length" class="empty-state padded">还没有知识库，请先创建一个。</p>
    </section>

    <section class="panel config-form">
      <div class="panel-head"><h2>创建知识库</h2><Plus :size="17" /></div>
      <form class="admin-form" @submit.prevent="createBase">
        <label>名称<input class="input field-input" name="name" required maxlength="128" placeholder="例如：退款政策库" /></label>
        <label>描述<textarea name="description" maxlength="500" placeholder="说明该知识库的业务范围"></textarea></label>
        <div class="form-actions"><button class="btn primary" :disabled="busy">{{ busy ? '处理中…' : '创建知识库' }}</button></div>
      </form>
    </section>
  </div>

  <section class="panel table-panel management-table">
    <div class="panel-head padded-head">
      <h2>{{ selectedBase ? `${selectedBase.name} · 文档` : '文档' }}</h2>
      <span class="toolbar-note">共 {{ documents.length }} 份</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>文档名称</th>
          <th>处理状态</th>
          <th>内容指纹</th>
          <th>文档 ID</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="document in documents" :key="document.id">
          <td><FileText :size="17" class="file-icon" /><strong>{{ document.fileName }}</strong></td>
          <td><span :class="`status ${statusClass(document.status)}`">{{ statusLabel(document.status) }}</span></td>
          <td>{{ document.contentHash?.slice(0, 16) || '—' }}…</td>
          <td>{{ document.id }}</td>
          <td>
            <button
              class="btn sm"
              :disabled="organizingDocId === document.id || busy"
              title="使用配置的 DeepSeek / OpenAI 模型提取摘要与标签"
              @click="handleOrganize(document)"
            >
              <LoaderCircle v-if="organizingDocId === document.id" :size="14" class="spin" />
              <Sparkles v-else :size="14" />
              {{ organizingDocId === document.id ? '整理中…' : '智能整理' }}
            </button>
          </td>
        </tr>
        <tr v-if="selectedBase && !documents.length"><td colspan="5">当前知识库还没有文档。</td></tr>
        <tr v-if="!selectedBase"><td colspan="5">选择或创建知识库后即可上传文档。</td></tr>
      </tbody>
    </table>
  </section>
</template>
