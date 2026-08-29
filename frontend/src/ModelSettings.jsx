import React, {useEffect, useState} from 'react';
import {Bot, CheckCircle2, Pencil, Plus, ShieldCheck, Sparkles, Wrench} from 'lucide-react';
import {
  createModelConfig,
  getModelConfigs,
  probeModelConnection,
  setDefaultModelConfig,
  setKnowledgeDefaultModelConfig,
  updateModelConfig
} from './api.js';

const initialForm = {
  name: '',
  protocol: 'OPENAI_COMPATIBLE',
  baseUrl: '',
  modelName: '',
  apiKey: '',
  isDefault: true,
  isKnowledgeDefault: false
};

export function ModelSettings({setNotice}) {
  const [models, setModels] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editingId, setEditingId] = useState(null); // null, 'new', or id
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => getModelConfigs().then(setModels).catch(loadError => setError(loadError.message));
  
  useEffect(() => {
    load();
  }, []);

  const update = event => setForm(current => ({
    ...current,
    [event.target.name]: event.target.type === 'checkbox' ? event.target.checked : event.target.value
  }));

  const startCreate = () => {
    setEditingId('new');
    setForm(initialForm);
    setError('');
  };

  const startEdit = model => {
    setEditingId(model.id);
    setForm({
      name: model.name,
      protocol: model.protocol,
      baseUrl: model.baseUrl,
      modelName: model.modelName,
      apiKey: '',
      isDefault: Boolean(model.isDefault),
      isKnowledgeDefault: Boolean(model.isKnowledgeDefault)
    });
    setError('');
  };

  const probe = async () => {
    if (!form.baseUrl) {
      setError('测试连接前请填写 Base URL。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await probeModelConnection(form);
      setNotice(result.reachable ? `连接成功：${result.message}` : `连接响应：${result.message}`);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setBusy(false);
    }
  };

  const save = async event => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (editingId === 'new' || !editingId) {
        if (!form.apiKey) {
          setError('新增模型必须填写 API Key。');
          setBusy(false);
          return;
        }
        await createModelConfig(form);
        setNotice('模型配置已加密保存。');
      } else {
        await updateModelConfig(editingId, form);
        setNotice('模型配置已就地更新。');
      }
      setEditingId(null);
      setForm(initialForm);
      await load();
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setBusy(false);
    }
  };

  const makeDefault = async model => {
    if (model.isDefault || busy) return;
    setBusy(true);
    setError('');
    try {
      await setDefaultModelConfig(model.id);
      await load();
      setNotice(`已切换默认客服推理模型：${model.name}`);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setBusy(false);
    }
  };

  const makeKnowledgeDefault = async model => {
    if (model.isKnowledgeDefault || busy) return;
    setBusy(true);
    setError('');
    try {
      await setKnowledgeDefaultModelConfig(model.id);
      await load();
      setNotice(`已切换知识库自动整理模型：${model.name}`);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setBusy(false);
    }
  };

  return <>
    <div className="page-header">
      <div>
        <h1>模型配置与场景路由</h1>
        <p>管理聊天推理、知识库整理协议、端点和加密凭据（支持 DeepSeek / OpenAI / Claude）</p>
      </div>
      <div className="header-actions">
        <button className="btn primary" onClick={startCreate}><Plus size={16}/>新增模型</button>
      </div>
    </div>
    {error && <p className="warning">{error}</p>}
    <div className="settings-grid">
      <section className="panel model-list">
        <h2>已配置模型</h2>
        {models.map(model => (
          <div className={'model-row ' + (model.isDefault ? 'selected ' : '') + (model.isKnowledgeDefault ? 'kb-selected' : '')} key={model.id}>
            <span className="model-icon"><Bot size={17}/></span>
            <div>
              <strong>{model.name} · {model.protocol}</strong>
              <small>{model.modelName} · {model.baseUrl}</small>
              <div className="model-inline-tags">
                {model.isDefault && <span className="badge badge-chat"><Sparkles size={11}/> 默认推理</span>}
                {model.isKnowledgeDefault && <span className="badge badge-kb"><Wrench size={11}/> 知识整理</span>}
              </div>
            </div>
            <div className="model-row-actions">
              <button className="btn sm" onClick={() => startEdit(model)}><Pencil size={13}/> 编辑</button>
              {!model.isDefault && <button className="btn sm" disabled={busy} onClick={() => makeDefault(model)}>设为默认</button>}
              {!model.isKnowledgeDefault && <button className="btn sm" disabled={busy} onClick={() => makeKnowledgeDefault(model)}>设为知识整理</button>}
            </div>
          </div>
        ))}
        {!models.length && <p className="empty-state padded">未接入云端模型。请添加并设为默认的云端模型配置（如 DeepSeek / OpenAI）后再开始 AI 会话。</p>}
      </section>

      <section className="panel config-form">
        <div className="panel-head">
          <h2>{editingId && editingId !== 'new' ? '就地编辑模型配置' : '新云端模型接入'}</h2>
          <span className="status success">AES-GCM 加密</span>
        </div>
        <form onSubmit={save} className="admin-form">
          <label>配置名称
            <input className="input field-input" name="name" value={form.name} onChange={update} required maxLength="128" placeholder="例如：DeepSeek 生产主力"/>
          </label>
          <label>协议类型
            <select className="input field-input" name="protocol" value={form.protocol} onChange={update}>
              <option value="OPENAI_COMPATIBLE">OPENAI_COMPATIBLE (DeepSeek / OpenAI)</option>
              <option value="ANTHROPIC_MESSAGES">ANTHROPIC_MESSAGES (Claude Messages)</option>
            </select>
          </label>
          <label>Base URL
            <input className="input field-input" name="baseUrl" value={form.baseUrl} onChange={update} required type="url" placeholder="https://api.deepseek.com/v1"/>
          </label>
          <label>模型名称
            <input className="input field-input" name="modelName" value={form.modelName} onChange={update} required placeholder="deepseek-chat / gpt-4o"/>
          </label>
          <label>API Key
            <input className="input field-input" name="apiKey" value={form.apiKey} onChange={update} type="password" autoComplete="off" placeholder={editingId && editingId !== 'new' ? '留空则保留原加密密钥' : '仅在保存时提交'}/>
          </label>
          <label className="check">
            <input name="isDefault" type="checkbox" checked={form.isDefault} onChange={update}/>
            设为当前租户默认客服推理模型
          </label>
          <label className="check">
            <input name="isKnowledgeDefault" type="checkbox" checked={form.isKnowledgeDefault} onChange={update}/>
            设为知识库自动整理模型 (DeepSeek / OpenAI)
          </label>
          <div className="form-actions">
            {editingId && <button className="btn" type="button" onClick={() => setEditingId(null)}>取消</button>}
            <button className="btn" type="button" disabled={busy} onClick={probe}>测试连接</button>
            <button className="btn primary" disabled={busy}>{busy ? '保存中…' : '保存配置'}</button>
          </div>
        </form>
        <p className="safe-note"><ShieldCheck size={15}/>API Key 采用 AES-GCM 加密，列表接口永不返回明文；网关按请求读取当前默认配置，切换后无需等待客户端缓存失效。</p>
      </section>
    </div>
  </>;
}
