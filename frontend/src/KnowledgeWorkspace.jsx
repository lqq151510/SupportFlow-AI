import React, {useEffect, useRef, useState} from 'react';
import {BookOpen, FileText, Plus, Upload} from 'lucide-react';
import {createKnowledgeBase, getKnowledgeBases, getKnowledgeDocuments, uploadKnowledgeDocument} from './api.js';

const statusLabel = status => ({UPLOADED: '已上传', PARSING: '解析中', CHUNKING: '切片中', EMBEDDING: '向量化中', INDEXED: '已索引', FAILED: '失败'})[status] || status;
const statusClass = status => status === 'INDEXED' ? 'success' : status === 'FAILED' ? 'danger' : 'processing';

export function KnowledgeWorkspace({setNotice}) {
  const [bases, setBases] = useState([]);
  const [selectedBase, setSelectedBase] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileInput = useRef(null);

  const loadBases = async preferredId => {
    const items = await getKnowledgeBases();
    setBases(items);
    setSelectedBase(current => items.find(item => item.id === (preferredId || current?.id)) || items[0] || null);
  };

  useEffect(() => {
    loadBases().catch(loadError => setError(loadError.message));
  }, []);

  useEffect(() => {
    if (!selectedBase) {
      setDocuments([]);
      return;
    }
    setError('');
    getKnowledgeDocuments(selectedBase.id).then(setDocuments).catch(loadError => setError(loadError.message));
  }, [selectedBase?.id]);

  const createBase = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    setError('');
    try {
      const values = new FormData(form);
      const created = await createKnowledgeBase({name: values.get('name'), description: values.get('description')});
      form.reset();
      await loadBases(created.id);
      setNotice('知识库已创建。');
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setBusy(false);
    }
  };

  const upload = async event => {
    const file = event.target.files?.[0];
    if (!file || !selectedBase) return;
    setBusy(true);
    setError('');
    try {
      await uploadKnowledgeDocument(selectedBase.id, file);
      setDocuments(await getKnowledgeDocuments(selectedBase.id));
      setNotice(`${file.name} 已上传并进入摄取流程。`);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      event.target.value = '';
      setBusy(false);
    }
  };

  return <>
    <div className="page-header"><div><h1>知识库管理</h1><p>按当前租户管理文档摄取、切片和索引</p></div><div className="header-actions"><input ref={fileInput} className="visually-hidden" type="file" accept=".pdf,.doc,.docx,.md,.txt" onChange={upload}/><button className="btn primary" disabled={!selectedBase || busy} onClick={() => fileInput.current?.click()}><Upload size={16}/>上传文档</button></div></div>
    {error && <p className="warning">{error}</p>}
    <div className="settings-grid">
      <section className="panel model-list"><h2>知识库</h2>{bases.map(item => <button className={'model-row model-row-button '+(selectedBase?.id === item.id ? 'selected' : '')} key={item.id} onClick={() => setSelectedBase(item)}><span className="model-icon"><BookOpen size={17}/></span><div><strong>{item.name}</strong><small>{item.description || '暂无描述'}</small></div><span className="status success">{item.status}</span></button>)}{!bases.length && <p className="empty-state padded">还没有知识库，请先创建一个。</p>}</section>
      <section className="panel config-form"><div className="panel-head"><h2>创建知识库</h2><Plus size={17}/></div><form onSubmit={createBase} className="admin-form"><label>名称<input className="input field-input" name="name" required maxLength="128" placeholder="例如：退款政策库"/></label><label>描述<textarea name="description" maxLength="500" placeholder="说明该知识库的业务范围"/></label><div className="form-actions"><button className="btn primary" disabled={busy}>{busy ? '处理中…' : '创建知识库'}</button></div></form></section>
    </div>
    <section className="panel table-panel management-table"><div className="panel-head padded-head"><h2>{selectedBase ? `${selectedBase.name} · 文档` : '文档'}</h2><span className="toolbar-note">共 {documents.length} 份</span></div><table><thead><tr><th>文档名称</th><th>处理状态</th><th>内容指纹</th><th>文档 ID</th></tr></thead><tbody>{documents.map(document => <tr key={document.id}><td><FileText size={17} className="file-icon"/><strong>{document.fileName}</strong></td><td><span className={'status '+statusClass(document.status)}>{statusLabel(document.status)}</span></td><td>{document.contentHash?.slice(0, 16) || '—'}…</td><td>{document.id}</td></tr>)}{selectedBase && !documents.length && <tr><td colSpan="4">当前知识库还没有文档。</td></tr>}{!selectedBase && <tr><td colSpan="4">选择或创建知识库后即可上传文档。</td></tr>}</tbody></table></section>
  </>;
}
