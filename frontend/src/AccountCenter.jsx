import React, {useEffect, useMemo, useState} from 'react';
import {
  Activity,
  Bot,
  CheckCircle2,
  Coins,
  Copy,
  DollarSign,
  KeyRound,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  UserRound,
  Wrench,
  X,
  Zap
} from 'lucide-react';
import {
  changePassword,
  createModelConfig,
  getModelConfigs,
  getModelUsageOverview,
  getMyProfile,
  getRecentModelUsages,
  probeModelConnection,
  setDefaultModelConfig,
  setKnowledgeDefaultModelConfig,
  updateModelConfig,
  updateMyProfile
} from './api.js';

const roleLabel = {
  TENANT_ADMIN: '工作区管理员',
  SUPERVISOR: '客服主管',
  AGENT: '客服坐席',
  CUSTOMER: '消费者',
};

const scenarioLabel = {
  CHAT: '客服智能会话',
  KNOWLEDGE_ORGANIZATION: '知识库自动整理',
  ASSISTANT: '智能助手问答',
  PROBE: '连接探测测试',
};

const initials = name => (name || 'U').trim().slice(0, 2).toLocaleUpperCase();
const formatJoinedAt = value => value ? new Intl.DateTimeFormat('zh-CN', {year: 'numeric', month: 'long', day: 'numeric'}).format(new Date(value)) : '—';
const formatTime = value => value ? new Intl.DateTimeFormat('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'}).format(new Date(value)) : '—';

export function AccountCenter({onProfileChange, onOpenModelSettings, setNotice, session}) {
  const [profile, setProfile] = useState(null);
  const [models, setModels] = useState([]);
  const [usageStats, setUsageStats] = useState(null);
  const [recentRecords, setRecentRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  
  // 个人资料编辑
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [saving, setSaving] = useState(false);
  
  // 修改密码
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [passwords, setPasswords] = useState({currentPassword: '', newPassword: '', confirmPassword: ''});
  const [passwordSaving, setPasswordSaving] = useState(false);

  // 就地模型编辑
  const [editingModelId, setEditingModelId] = useState(null); // 'new' 或 modelId
  const [modelForm, setModelForm] = useState({
    name: '',
    protocol: 'OPENAI_COMPATIBLE',
    baseUrl: '',
    modelName: '',
    apiKey: '',
    isDefault: false,
    isKnowledgeDefault: false,
  });
  const [modelSaving, setModelSaving] = useState(false);

  const isAdmin = session.role === 'TENANT_ADMIN';
  const defaultChatModel = useMemo(() => models.find(model => model.isDefault) || null, [models]);
  const defaultKnowledgeModel = useMemo(() => models.find(model => model.isKnowledgeDefault) || defaultChatModel, [models, defaultChatModel]);

  const loadData = async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    setError('');
    try {
      const [loadedProfile, loadedModels, loadedStats, loadedRecent] = await Promise.all([
        getMyProfile(),
        isAdmin ? getModelConfigs() : Promise.resolve([]),
        isAdmin ? getModelUsageOverview().catch(() => null) : Promise.resolve(null),
        isAdmin ? getRecentModelUsages(15).catch(() => []) : Promise.resolve([]),
      ]);
      setProfile(loadedProfile);
      setDisplayName(loadedProfile.displayName);
      setModels(loadedModels);
      setUsageStats(loadedStats);
      setRecentRecords(loadedRecent || []);
      onProfileChange(loadedProfile);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [isAdmin]);

  const saveProfile = async event => {
    event.preventDefault();
    if (!displayName.trim() || saving) return;
    setSaving(true);
    try {
      const updated = await updateMyProfile({displayName: displayName.trim()});
      setProfile(updated);
      setDisplayName(updated.displayName);
      onProfileChange(updated);
      setEditing(false);
      setNotice('个人资料已保存。');
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  };

  const savePassword = async event => {
    event.preventDefault();
    if (passwordSaving) return;
    if (passwords.newPassword !== passwords.confirmPassword) {
      setError('两次输入的新密码不一致。');
      return;
    }
    setPasswordSaving(true);
    try {
      await changePassword(passwords);
      setPasswords({currentPassword: '', newPassword: '', confirmPassword: ''});
      setPasswordOpen(false);
      setNotice('密码已更新；其他已登录设备的会话已失效。');
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setPasswordSaving(false);
    }
  };

  const copyWorkspaceCode = async () => {
    try {
      await navigator.clipboard.writeText(profile.tenantCode);
      setNotice('工作区代码已复制。');
    } catch {
      setError('无法访问系统剪贴板，请手动复制工作区代码。');
    }
  };

  // 就地模型编辑逻辑
  const startEditModel = (model) => {
    if (model) {
      setEditingModelId(model.id);
      setModelForm({
        name: model.name,
        protocol: model.protocol,
        baseUrl: model.baseUrl,
        modelName: model.modelName,
        apiKey: '', // 留空表示不修改已有 Key
        isDefault: Boolean(model.isDefault),
        isKnowledgeDefault: Boolean(model.isKnowledgeDefault),
      });
    } else {
      setEditingModelId('new');
      setModelForm({
        name: '',
        protocol: 'OPENAI_COMPATIBLE',
        baseUrl: 'https://api.deepseek.com/v1',
        modelName: 'deepseek-chat',
        apiKey: '',
        isDefault: models.length === 0,
        isKnowledgeDefault: models.length === 0,
      });
    }
  };

  const cancelEditModel = () => {
    setEditingModelId(null);
    setError('');
  };

  const probeCurrentForm = async () => {
    if (!modelForm.baseUrl) {
      setError('测试连接前请填写 Base URL。');
      return;
    }
    setModelSaving(true);
    setError('');
    try {
      const result = await probeModelConnection({baseUrl: modelForm.baseUrl, apiKey: modelForm.apiKey || 'test'});
      setNotice(result.reachable ? `连接探测成功：${result.message}` : `探测响应：${result.message}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setModelSaving(false);
    }
  };

  const saveModelForm = async (event) => {
    event.preventDefault();
    setModelSaving(true);
    setError('');
    try {
      if (editingModelId === 'new') {
        if (!modelForm.apiKey) {
          setError('新建模型源必须填写 API Key。');
          setModelSaving(false);
          return;
        }
        await createModelConfig(modelForm);
        setNotice('新模型源已加密接入并保存。');
      } else {
        await updateModelConfig(editingModelId, modelForm);
        setNotice('模型配置已原地更新并加密保存。');
      }
      setEditingModelId(null);
      await loadData(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setModelSaving(false);
    }
  };

  const handleSetChatDefault = async (modelId) => {
    setModelSaving(true);
    try {
      await setDefaultModelConfig(modelId);
      await loadData(true);
      setNotice('已切换当前租户默认推理/客服模型。');
    } catch (err) {
      setError(err.message);
    } finally {
      setModelSaving(false);
    }
  };

  const handleSetKnowledgeDefault = async (modelId) => {
    setModelSaving(true);
    try {
      await setKnowledgeDefaultModelConfig(modelId);
      await loadData(true);
      setNotice('已切换当前租户知识库自动整理模型。');
    } catch (err) {
      setError(err.message);
    } finally {
      setModelSaving(false);
    }
  };

  if (loading) return <div className="account-loading"><LoaderCircle size={20} className="spin"/><span>正在读取你的本地账户与数据看板…</span></div>;
  if (!profile) return <section className="account-error panel"><h1>个人中心暂不可用</h1><p>{error || '无法读取当前账户资料。'}</p><button className="btn" onClick={() => loadData()}>重新加载</button></section>;

  const totalCalls = usageStats?.totalCalls || 0;
  const totalTokens = usageStats?.totalTokens || 0;
  const totalInputTokens = usageStats?.totalInputTokens || 0;
  const totalOutputTokens = usageStats?.totalOutputTokens || 0;
  const avgLatency = usageStats?.averageLatencyMs || 0;
  const costCny = usageStats?.totalEstimatedCostCny ? Number(usageStats.totalEstimatedCostCny).toFixed(4) : '0.0000';
  const costUsd = usageStats?.totalEstimatedCostUsd ? Number(usageStats.totalEstimatedCostUsd).toFixed(4) : '0.0000';

  return <div className="account-center">
    {/* 头部 Hero */}
    <section className="account-hero">
      <div className="account-hero-glow"/>
      <div className="account-avatar large">{initials(profile.displayName)}</div>
      <div className="account-identity">
        <div className="eyebrow-row">
          <span className="eyebrow">PERSONAL CONSOLE</span>
          <span className="shortcut-tag"><kbd>⌘</kbd> <kbd>,</kbd> 快捷唤出/切回</span>
        </div>
        <h1>{profile.displayName}</h1>
        <p>{roleLabel[profile.role] || profile.role} · {profile.tenantName}</p>
      </div>
      <div className="account-security-badge">
        <ShieldCheck size={18}/><span>多租户加密隔离</span>
        <button className="icon-btn-ghost" title="刷新数据" onClick={() => loadData(true)}>
          <RefreshCcw size={16} className={refreshing ? 'spin' : ''}/>
        </button>
      </div>
    </section>

    {error && <p className="warning account-warning"><X size={15}/>{error}</p>}

    {/* 数据看板：全链路真实 Token 归集与费用核算 (Optimization 1 & 3) */}
    {isAdmin && <section className="panel account-usage-dashboard">
      <div className="panel-head">
        <div className="head-title">
          <Coins size={20} className="icon-gold"/>
          <div>
            <h2>真实 API 费用与 Token 归集看板</h2>
            <p>全链路自动记录会话交互、知识库整理与模型测试的真实消耗与经济成本</p>
          </div>
        </div>
        <div className="dashboard-badges">
          <span className="status success"><Activity size={14}/> 实时入库</span>
        </div>
      </div>

      <div className="usage-stats-grid">
        <div className="stat-card cost-highlight">
          <span className="stat-label">预估累计调用成本 (CNY)</span>
          <strong className="stat-value cny-amount">¥ {costCny}</strong>
          <small className="stat-sub">折合美元 ≈ ${costUsd} (汇率 7.2)</small>
        </div>

        <div className="stat-card">
          <span className="stat-label">累计消耗总 Token</span>
          <strong className="stat-value">{totalTokens.toLocaleString()}</strong>
          <small className="stat-sub">输入 {totalInputTokens.toLocaleString()} · 输出 {totalOutputTokens.toLocaleString()}</small>
        </div>

        <div className="stat-card">
          <span className="stat-label">全场景模型调用次数</span>
          <strong className="stat-value">{totalCalls.toLocaleString()} 次</strong>
          <small className="stat-sub">平均响应耗时 {avgLatency} ms</small>
        </div>
      </div>

      {/* 场景与模型分布 */}
      <div className="usage-breakdown-row">
        <div className="breakdown-box">
          <span className="box-title"><Zap size={15}/> 场景分布</span>
          <div className="scenario-bars">
            {usageStats?.scenarioCalls && Object.keys(usageStats.scenarioCalls).length > 0 ? (
              Object.entries(usageStats.scenarioCalls).map(([sc, count]) => {
                const percent = totalCalls > 0 ? Math.round((count / totalCalls) * 100) : 0;
                return (
                  <div className="bar-item" key={sc}>
                    <div className="bar-info">
                      <span>{scenarioLabel[sc] || sc}</span>
                      <b>{count} 次 ({percent}%)</b>
                    </div>
                    <div className="progress mini"><span style={{width: `${percent}%`}}/></div>
                  </div>
                );
              })
            ) : (
              <p className="empty-sub">暂无多场景调用记录，进行客服会话或知识库整理后将实时更新。</p>
            )}
          </div>
        </div>

        <div className="breakdown-box">
          <span className="box-title"><DollarSign size={15}/> 模型消费与 Token 分布</span>
          <div className="model-breakdown-list">
            {usageStats?.modelTokens && Object.keys(usageStats.modelTokens).length > 0 ? (
              Object.entries(usageStats.modelTokens).map(([model, tCount]) => {
                const cny = usageStats?.modelCostCny?.[model] ? Number(usageStats.modelCostCny[model]).toFixed(4) : '0.0000';
                return (
                  <div className="model-cost-row" key={model}>
                    <div className="model-name-col">
                      <strong>{model}</strong>
                      <small>{tCount.toLocaleString()} Tokens</small>
                    </div>
                    <span className="model-cost-badge">¥ {cny}</span>
                  </div>
                );
              })
            ) : (
              <p className="empty-sub">支持 DeepSeek / OpenAI 等模型定价，接入后自动核算单次开销。</p>
            )}
          </div>
        </div>
      </div>
    </section>}

    <div className="account-grid">
      {/* 账户资料 */}
      <section className="panel account-card account-profile-card">
        <div className="panel-head">
          <div><span className="eyebrow">ACCOUNT</span><h2>账户资料</h2></div>
          {!editing && <button className="btn" onClick={() => setEditing(true)}><Pencil size={15}/>编辑资料</button>}
        </div>
        {editing ? <form className="account-form" onSubmit={saveProfile}>
          <label>显示名称<input className="input field-input" value={displayName} maxLength="128" onChange={event => setDisplayName(event.target.value)} required autoComplete="name"/></label>
          <div className="form-actions"><button className="btn" type="button" onClick={() => {setEditing(false); setDisplayName(profile.displayName);}}>取消</button><button className="btn primary" disabled={saving}>{saving ? '保存中…' : '保存资料'}</button></div>
        </form> : <dl className="account-details">
          <div><dt>邮箱</dt><dd>{profile.email}</dd></div>
          <div><dt>角色</dt><dd>{roleLabel[profile.role] || profile.role}</dd></div>
          <div><dt>加入工作区</dt><dd>{formatJoinedAt(profile.joinedAt)}</dd></div>
        </dl>}
      </section>

      {/* 当前工作区 */}
      <section className="panel account-card workspace-card">
        <div className="panel-head"><div><span className="eyebrow">WORKSPACE</span><h2>当前工作区</h2></div><UserRound size={19}/></div>
        <strong>{profile.tenantName}</strong>
        <p>当前账号在工作区内角色为{roleLabel[profile.role] || profile.role}。租户与模型数据由 JWT 上下文严格隔离。</p>
        <div className="workspace-code"><span>租户代码</span><code>{profile.tenantCode}</code><button className="icon-btn" aria-label="复制工作区代码" onClick={copyWorkspaceCode}><Copy size={16}/></button></div>
        {isAdmin && <button className="btn model-settings-link" onClick={onOpenModelSettings}>前往设置管理模型与通知</button>}
      </section>

      {/* 模型 API 接入与就地编辑卡片 (Optimization 2 & 4) */}
      <section className="panel account-card model-access-card full-width">
        <div className="panel-head">
          <div><span className="eyebrow">AI MODEL ROUTING</span><h2>模型 API 接入与场景路由</h2></div>
          {isAdmin && !editingModelId && (
            <button className="btn primary" onClick={() => startEditModel(null)}>
              <Plus size={16}/>接入新模型 (DeepSeek / OpenAI)
            </button>
          )}
        </div>

        {isAdmin ? (
          <>
            {/* 就地编辑表单 */}
            {editingModelId && (
              <form className="inline-model-editor panel" onSubmit={saveModelForm}>
                <div className="editor-head">
                  <h3>{editingModelId === 'new' ? '接入新云端模型源' : '就地编辑模型配置'}</h3>
                  <span className="safe-tag"><ShieldCheck size={14}/> AES-GCM 密文存储</span>
                </div>
                <div className="editor-grid">
                  <label>配置名称
                    <input className="input field-input" value={modelForm.name} onChange={e => setModelForm({...modelForm, name: e.target.value})} required placeholder="例如：DeepSeek 生产主力 / GPT-4o 整理"/>
                  </label>
                  <label>协议类型
                    <select className="input field-input" value={modelForm.protocol} onChange={e => setModelForm({...modelForm, protocol: e.target.value})}>
                      <option value="OPENAI_COMPATIBLE">OPENAI_COMPATIBLE (DeepSeek / OpenAI / 本地兼容)</option>
                      <option value="ANTHROPIC_MESSAGES">ANTHROPIC_MESSAGES (Claude Messages)</option>
                    </select>
                  </label>
                  <label>Base URL
                    <input className="input field-input" type="url" value={modelForm.baseUrl} onChange={e => setModelForm({...modelForm, baseUrl: e.target.value})} required placeholder="https://api.deepseek.com/v1"/>
                  </label>
                  <label>模型名称 (Model Identifier)
                    <input className="input field-input" value={modelForm.modelName} onChange={e => setModelForm({...modelForm, modelName: e.target.value})} required placeholder="deepseek-chat / gpt-4o"/>
                  </label>
                  <label className="full-col">API Key
                    <input className="input field-input" type="password" value={modelForm.apiKey} onChange={e => setModelForm({...modelForm, apiKey: e.target.value})} placeholder={editingModelId === 'new' ? '输入模型 API Key' : '留空则保留原有加密密钥'} autoComplete="off"/>
                  </label>
                </div>
                <div className="checkbox-row">
                  <label className="check">
                    <input type="checkbox" checked={modelForm.isDefault} onChange={e => setModelForm({...modelForm, isDefault: e.target.checked})}/>
                    设为默认客服推理模型 (Chat Default)
                  </label>
                  <label className="check">
                    <input type="checkbox" checked={modelForm.isKnowledgeDefault} onChange={e => setModelForm({...modelForm, isKnowledgeDefault: e.target.checked})}/>
                    设为知识库自动整理模型 (Knowledge Default)
                  </label>
                </div>
                <div className="editor-actions">
                  <button className="btn" type="button" onClick={cancelEditModel}>取消</button>
                  <button className="btn" type="button" disabled={modelSaving} onClick={probeCurrentForm}>测试端点连接</button>
                  <button className="btn primary" disabled={modelSaving}>{modelSaving ? '保存中…' : '保存模型配置'}</button>
                </div>
              </form>
            )}

            {/* 模型列表 */}
            <div className="model-cards-list">
              {models.map(model => (
                <div className={'model-item-card ' + (model.isDefault ? 'active-chat ' : '') + (model.isKnowledgeDefault ? 'active-kb' : '')} key={model.id}>
                  <div className="model-item-header">
                    <div className="model-title-wrap">
                      <span className="model-avatar"><Bot size={18}/></span>
                      <div>
                        <strong>{model.name}</strong>
                        <small>{model.modelName} · {model.protocol}</small>
                      </div>
                    </div>
                    <div className="model-tags">
                      {model.isDefault && <span className="badge badge-chat"><Sparkles size={12}/> 默认客服推理</span>}
                      {model.isKnowledgeDefault && <span className="badge badge-kb"><Wrench size={12}/> 知识库整理模型</span>}
                    </div>
                  </div>

                  <div className="model-url-line">
                    <code>{model.baseUrl}</code>
                  </div>

                  <div className="model-card-actions">
                    <button className="btn sm" onClick={() => startEditModel(model)}>
                      <Pencil size={13}/>就地编辑
                    </button>
                    {!model.isDefault && (
                      <button className="btn sm" disabled={modelSaving} onClick={() => handleSetChatDefault(model.id)}>
                        设为默认推理
                      </button>
                    )}
                    {!model.isKnowledgeDefault && (
                      <button className="btn sm" disabled={modelSaving} onClick={() => handleSetKnowledgeDefault(model.id)}>
                        设为知识整理
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {!models.length && !editingModelId && (
                <div className="model-empty-box">
                  <Bot size={32}/>
                  <strong>暂未接入任何云端模型 API</strong>
                  <p>点击上方“接入新模型”，即可接入 DeepSeek、OpenAI 或 Claude 等端点，系统将自动启用智能问答与知识库智能整理。</p>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="model-empty-box">
            <Bot size={28}/>
            <strong>模型由工作区管理员统一配置</strong>
            <p>当前账号可体验已启用的 AI 客服与知识库整理能力。</p>
          </div>
        )}
      </section>

      {/* 真实调用流水记录表格 (Optimization 1 & 3) */}
      {isAdmin && <section className="panel account-card recent-usages-card full-width">
        <div className="panel-head">
          <div>
            <span className="eyebrow">AUDIT & TRACE</span>
            <h2>最近模型调用流水 (Real-time Usage Log)</h2>
          </div>
          <button className="btn sm" onClick={() => loadData(true)}><RefreshCcw size={14}/> 刷新流水</button>
        </div>
        <div className="table-responsive">
          <table className="usage-table">
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
              {recentRecords.map(record => (
                <tr key={record.id}>
                  <td><small>{formatTime(record.createdAt)}</small></td>
                  <td><span className="badge-scenario">{scenarioLabel[record.scenario] || record.scenario}</span></td>
                  <td><strong>{record.modelName}</strong></td>
                  <td>{record.inputTokens.toLocaleString()}</td>
                  <td>{record.outputTokens.toLocaleString()}</td>
                  <td><b>{record.totalTokens.toLocaleString()}</b></td>
                  <td>{record.latencyMs} ms</td>
                  <td className="cost-cell">¥ {Number(record.estimatedCostCny || 0).toFixed(5)}</td>
                </tr>
              ))}
              {!recentRecords.length && (
                <tr>
                  <td colSpan="8" className="empty-cell">当前还没有调用记录，发起客服对话或整理知识库后将在此实时展示。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>}

      {/* 账户安全 */}
      <section className="panel account-card account-security-card full-width">
        <div className="panel-head"><div><span className="eyebrow">SECURITY</span><h2>账户安全</h2></div><KeyRound size={19}/></div>
        <p>修改密码后，当前工作区下的刷新令牌会被立即撤销；其他已登录设备的会话将自动失效。</p>
        <button className="btn" onClick={() => {setPasswordOpen(value => !value); setError('');}}>{passwordOpen ? '收起修改密码' : '修改密码'}</button>
        {passwordOpen && <form className="account-form password-form" onSubmit={savePassword}>
          <label>当前密码<input className="input field-input" type="password" value={passwords.currentPassword} onChange={event => setPasswords(value => ({...value, currentPassword: event.target.value}))} required autoComplete="current-password"/></label>
          <label>新密码<input className="input field-input" type="password" minLength="12" value={passwords.newPassword} onChange={event => setPasswords(value => ({...value, newPassword: event.target.value}))} required autoComplete="new-password"/></label>
          <label>确认新密码<input className="input field-input" type="password" minLength="12" value={passwords.confirmPassword} onChange={event => setPasswords(value => ({...value, confirmPassword: event.target.value}))} required autoComplete="new-password"/></label>
          <div className="form-actions"><button className="btn primary" disabled={passwordSaving}>{passwordSaving ? '更新中…' : '确认更新密码'}</button></div>
        </form>}
      </section>
    </div>
  </div>;
}
