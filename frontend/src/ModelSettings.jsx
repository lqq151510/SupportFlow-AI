import React, {useEffect, useState} from 'react';
import {Bot, Plus, ShieldCheck} from 'lucide-react';
import {createModelConfig, getModelConfigs, probeModelConnection, setDefaultModelConfig} from './api.js';

const initialForm = {name: '', protocol: 'OPENAI_COMPATIBLE', baseUrl: '', modelName: '', apiKey: '', isDefault: true};

export function ModelSettings({setNotice}) {
  const [models, setModels] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => getModelConfigs().then(setModels).catch(loadError => setError(loadError.message));
  useEffect(() => {
    load();
  }, []);
  const update = event => setForm(current => ({...current, [event.target.name]: event.target.type === 'checkbox' ? event.target.checked : event.target.value}));

  const probe = async () => {
    if (!form.baseUrl || !form.apiKey) {
      setError('测试连接前请填写 Base URL 和 API Key。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await probeModelConnection(form);
      setNotice(result.reachable ? `连接成功：${result.message}` : `连接失败：${result.message}`);
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
      await createModelConfig(form);
      setForm(initialForm);
      await load();
      setNotice('模型配置已加密保存。');
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
      setNotice(`已切换默认模型：${model.name}`);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setBusy(false);
    }
  };

  return <>
    <div className="page-header"><div><h1>模型配置</h1><p>管理聊天模型协议、端点和加密凭据</p></div><div className="header-actions"><button className="btn primary" onClick={() => setForm(initialForm)}><Plus size={16}/>新增模型</button></div></div>
    {error && <p className="warning">{error}</p>}
    <div className="settings-grid"><section className="panel model-list"><h2>已配置模型</h2>{models.map(model => <div className={'model-row '+(model.isDefault ? 'selected' : '')} key={model.id}><span className="model-icon"><Bot size={17}/></span><div><strong>{model.name} · {model.protocol}</strong><small>{model.modelName} · {model.baseUrl}</small></div>{model.isDefault?<span className="status success">默认</span>:<button className="btn" disabled={busy} onClick={()=>makeDefault(model)}>设为默认</button>}</div>)}{!models.length && <p className="empty-state padded">当前租户还没有模型配置。</p>}</section><section className="panel config-form"><div className="panel-head"><h2>新模型配置</h2><span className="status success">密钥只写入</span></div><form onSubmit={save} className="admin-form"><label>配置名称<input className="input field-input" name="name" value={form.name} onChange={update} required maxLength="128" placeholder="客服主模型"/></label><label>协议类型<select className="input field-input" name="protocol" value={form.protocol} onChange={update}><option value="OPENAI_COMPATIBLE">OPENAI_COMPATIBLE</option><option value="ANTHROPIC_MESSAGES">ANTHROPIC_MESSAGES</option></select></label><label>Base URL<input className="input field-input" name="baseUrl" value={form.baseUrl} onChange={update} required type="url" placeholder="https://api.example.com/v1"/></label><label>模型名称<input className="input field-input" name="modelName" value={form.modelName} onChange={update} required placeholder="model-name"/></label><label>API Key<input className="input field-input" name="apiKey" value={form.apiKey} onChange={update} required type="password" autoComplete="off" placeholder="仅在保存时提交"/></label><label className="check"><input name="isDefault" type="checkbox" checked={form.isDefault} onChange={update}/>设为当前租户默认聊天模型</label><div className="form-actions"><button className="btn" type="button" disabled={busy} onClick={probe}>测试连接</button><button className="btn primary" disabled={busy}>{busy ? '保存中…' : '保存配置'}</button></div></form><p className="safe-note"><ShieldCheck size={15}/>API Key 使用 AES-GCM 加密，列表接口永不返回明文；网关按请求读取当前默认配置，切换后无需等待客户端缓存失效。</p></section></div>
  </>;
}
