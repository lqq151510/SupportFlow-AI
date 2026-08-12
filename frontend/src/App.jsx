import React, {useEffect, useRef, useState} from 'react';
import {addTicketComment, changeTicketStatus, claimTicket, createConversation, decideApproval, getApprovals, getCustomerOrders, getOperationsOverview, getSession, getTicketComments, getTickets, login, readGenerationEvents, registerCustomer, submitCustomerMessage} from './api.js';
import {createRoot} from 'react-dom/client';
import {LayoutDashboard, Ticket, Users, BookOpen, Workflow, BarChart3, Settings, Search, Bell, MessageSquare, ChevronDown, Plus, Upload, FileText, CheckCircle2, Clock3, AlertTriangle, ArrowRight, Bot, ShieldCheck, SlidersHorizontal, Send, ExternalLink, RefreshCcw, ClipboardList} from 'lucide-react';
import './styles.css';
import {KnowledgeWorkspace} from './KnowledgeWorkspace.jsx';
import {ModelSettings} from './ModelSettings.jsx';
import {AnalyticsWorkspace} from './AnalyticsWorkspace.jsx';

const nav = [
  ['概览','overview',LayoutDashboard], ['工单','tickets',Ticket], ['客户','customers',Users], ['知识库','knowledge',BookOpen], ['自动化','automation',Workflow], ['分析','analytics',BarChart3], ['设置','settings',Settings]
];
const agentNav = nav.filter(([, key]) => key !== 'customers');
const customerNav = [['我的服务', 'customers', Users]];
const tickets = [
  {id:'TKT-52418', title:'订单退款与退货运费咨询', customer:'林小满', priority:'高', status:'处理中', sla:'剩余 42 分钟'},
  {id:'TKT-52417', title:'包裹超过预计送达时间', customer:'陈可', priority:'普通', status:'等待客户', sla:'剩余 2 小时'},
  {id:'TKT-52416', title:'商品破损申请补偿', customer:'周宁', priority:'紧急', status:'待审批', sla:'已超时 18 分钟'},
  {id:'TKT-52415', title:'修改收货地址', customer:'赵琳', priority:'低', status:'已解决', sla:'已完成'}
];

export function App(){
  const [session,setSession] = useState(undefined);
  useEffect(()=>{getSession().then(setSession).catch(()=>localStorage.removeItem('supportflow.accessToken')).finally(()=>setSession(current=>current===undefined?null:current));},[]);
  if(session===undefined)return <div className="login-shell">正在验证登录状态…</div>;
  return session?<Workspace session={session}/>:<LoginPage onSignedIn={setSession}/>;
}

function Workspace({session}){
  const [page,setPage] = useState(session.role==='CUSTOMER'?'customers':'overview');
  const [selected,setSelected] = useState(tickets[0]);
  const [notice,setNotice] = useState('');
  const [overview,setOverview] = useState(null);
  const [workspaceTickets,setWorkspaceTickets] = useState(tickets);
  const nav = session.role==='CUSTOMER'?customerNav:agentNav;
  useEffect(()=>{if(session.role==='CUSTOMER')return;getOperationsOverview().then(setOverview).catch(error=>setNotice(error.message));},[session.role]);
  useEffect(()=>{if(session.role==='CUSTOMER')return;getTickets().then(items=>{const normalized=items.map(toWorkspaceTicket);if(normalized.length){setWorkspaceTickets(normalized);setSelected(normalized[0]);}}).catch(error=>setNotice(error.message));},[session.role]);
  const navTo = (key)=>{setPage(key); setNotice('')};
  return <div className="app-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">◉</span><span>SupportFlow AI</span></div><div className="global-search"><Search size={17}/><span>搜索工单、客户、文档…</span><kbd>⌘ K</kbd></div><div className="top-actions"><Bell size={19}/><span className="notification">3</span><MessageSquare size={19}/><div className="online"><i/>在线</div><div className="avatar">AS</div><ChevronDown size={16}/></div></header>
    <div className="workspace"><aside className="sidebar"><nav>{nav.map(([label,key,Icon])=><button key={key} className={page===key?'active':''} onClick={()=>navTo(key)}><Icon size={19}/><span>{label}</span>{key==='tickets'&&<b>{workspaceTickets.length}</b>}</button>)}</nav><div className="vector-health"><div className="health-title">向量存储健康度 <CheckCircle2 size={15}/></div><strong>按知识库查看</strong><p>实时状态请进入知识库管理</p><div className="progress"><span style={{width:'100%'}}/></div></div><div className="tenant"><div className="avatar">AS</div><div><strong>当前租户</strong><small>{session.role}</small></div><ChevronDown size={16}/></div></aside><main className="main-content">{page==='overview'&&<Overview onNav={navTo} overview={overview} tickets={workspaceTickets}/>} {page==='knowledge'&&<KnowledgeWorkspace setNotice={setNotice}/>} {page==='tickets'&&<Tickets tickets={workspaceTickets} selected={selected} setSelected={setSelected} setWorkspaceTickets={setWorkspaceTickets} notice={notice} setNotice={setNotice}/>} {page==='customers'&&<Customer/>} {page==='analytics'&&<AnalyticsWorkspace overview={overview}/>} {page==='settings'&&<ModelSettings setNotice={setNotice}/>} {page==='automation'&&<Approvals notice={notice} setNotice={setNotice}/>}</main></div>
    {notice&&<div className="toast"><CheckCircle2 size={17}/>{notice}</div>}
  </div>
}

const priorityLabel=(priority)=>({LOW:'低',NORMAL:'普通',HIGH:'高',URGENT:'紧急'})[priority]||priority;
const statusLabel=(status)=>({NEW:'待处理',OPEN:'处理中',PENDING_CUSTOMER:'等待客户',PENDING_APPROVAL:'待审批',RESOLVED:'已解决',CLOSED:'已关闭'})[status]||status;
const slaLabel=(dueAt)=>{const minutes=Math.round((new Date(dueAt).getTime()-Date.now())/60000);return minutes<0?`已超时 ${Math.abs(minutes)} 分钟`:`剩余 ${minutes} 分钟`;};
const toWorkspaceTicket=(ticket)=>({rawId:ticket.id,id:`TKT-${ticket.id}`,title:ticket.title,customer:`客户 #${ticket.customerId}`,priority:priorityLabel(ticket.priority),status:statusLabel(ticket.status),statusCode:ticket.status,assignedMembershipId:ticket.assignedMembershipId,sla:slaLabel(ticket.resolutionDueAt)});

function LoginPage({onSignedIn}) {
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState('login');
  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    const values = new FormData(event.currentTarget);
    try {
      if (mode === 'register') await registerCustomer({tenantCode:values.get('tenantCode'), email:values.get('email'), displayName:values.get('displayName'), password:values.get('password')});
      const tokens = await login({tenantCode:values.get('tenantCode'), email:values.get('email'), password:values.get('password')});
      localStorage.setItem('supportflow.accessToken', tokens.accessToken);
      localStorage.setItem('supportflow.refreshToken', tokens.refreshToken);
      onSignedIn(await getSession());
    } catch (loginError) {
      localStorage.removeItem('supportflow.accessToken');
      localStorage.removeItem('supportflow.refreshToken');
      setError(loginError.message);
    } finally {
      setSubmitting(false);
    }
  };
  const registering = mode === 'register';
  return <main className="login-shell"><section className="panel login-panel"><div className="brand"><span className="brand-mark">◉</span><span>SupportFlow AI</span></div><h1>{registering?'创建消费者账户':'登录服务工作台'}</h1><p>{registering?'注册后会自动生成可演示的订单并进入消费者服务页。':'使用租户代码、邮箱和密码进入消费者或坐席视图。'}</p><form onSubmit={submit}><label>租户代码<input className="input field" name="tenantCode" required autoComplete="organization"/></label>{registering&&<label>显示名称<input className="input field" name="displayName" required autoComplete="name"/></label>}<label>邮箱<input className="input field" name="email" type="email" required autoComplete="email"/></label><label>密码<input className="input field" name="password" type="password" required minLength="12" autoComplete={registering?'new-password':'current-password'}/></label>{error&&<p className="warning"><AlertTriangle size={15}/>{error}</p>}<Button primary>{submitting?(registering?'注册中…':'登录中…'):(registering?'注册并登录':'登录')}</Button></form><button className="text-link" onClick={()=>{setMode(registering?'login':'register');setError('');}}>{registering?'已有账户？返回登录':'新用户？注册消费者账户'}</button><p className="safe-note"><ShieldCheck size={15}/>登录令牌只保存在当前浏览器本地存储中。</p></section></main>;
}

function Approvals({setNotice}) {
  const [approvals, setApprovals] = useState([]);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [pending, setPending] = useState(false);
  const idempotencyKeys = useRef(new Map());
  useEffect(() => {
    getApprovals().then(items => {
      setApprovals(items);
      setSelectedApproval(items[0] || null);
    }).catch(error => setNotice(error.message));
  }, [setNotice]);
  const decide = async (decision) => {
    if (!selectedApproval || selectedApproval.status !== 'PENDING' || pending) return;
    setPending(true);
    try {
      const keyId = `${selectedApproval.id}:${decision}`;
      const idempotencyKey = idempotencyKeys.current.get(keyId) || crypto.randomUUID();
      idempotencyKeys.current.set(keyId, idempotencyKey);
      const updated = await decideApproval(selectedApproval.id, decision, idempotencyKey);
      setApprovals(items => items.map(item => item.id === updated.id ? updated : item));
      setSelectedApproval(updated);
      idempotencyKeys.current.delete(keyId);
      setNotice(decision === 'APPROVED' ? '审批已批准，已创建后续执行任务。' : '审批已拒绝。');
    } catch (error) {
      setNotice(error.message);
    } finally {
      setPending(false);
    }
  };
  const pendingCount = approvals.filter(item => item.status === 'PENDING').length;
  return <><PageHeader title="高风险操作审批" sub="退款与补偿需要主管确认后执行"><Button>全部申请 <ChevronDown size={14}/></Button></PageHeader><div className="tabs"><button className="selected">待我审批 <b>{pendingCount}</b></button><button>全部申请</button><button>执行记录</button></div><div className="approval-layout"><section className="panel table-panel"><table><thead><tr><th>申请编号</th><th>操作</th><th>动作摘要</th><th>风险</th><th>状态</th><th>到期时间</th></tr></thead><tbody>{approvals.map(item => <tr key={item.id} onClick={() => setSelectedApproval(item)}><td><strong>APR-{item.id}</strong></td><td>{approvalActionLabel(item.actionType)}</td><td>{item.actionSummary}</td><td><span className="priority danger">高</span></td><td><span className={'status '+approvalStatusClass(item.status)}>{approvalStatusLabel(item.status)}</span></td><td>{formatDateTime(item.expiresAt)}</td></tr>)}{!approvals.length && <tr><td colSpan="6">当前没有审批申请</td></tr>}</tbody></table></section><aside className="panel approval-detail">{selectedApproval ? <><div className="panel-head"><h2>{approvalActionLabel(selectedApproval.actionType)}详情</h2><span className={'status '+approvalStatusClass(selectedApproval.status)}>{approvalStatusLabel(selectedApproval.status)}</span></div><p className="detail-label">APR-{selectedApproval.id}</p><div className="approval-summary"><strong>{selectedApproval.actionSummary}</strong><span>高风险操作，需人工确认</span><small>到期时间：{formatDateTime(selectedApproval.expiresAt)}</small></div><h3>审核提示</h3><div className="evidence-line"><CheckCircle2/>请核对订单、金额和退款资格</div><div className="evidence-line"><CheckCircle2/>批准后只会创建可靠执行任务</div><textarea placeholder="审批意见（可选）"/><label className="check"><input type="checkbox"/> 我已核对业务依据和操作范围</label><div className="approval-actions"><Button onClick={() => decide('REJECTED')}>{pending ? '处理中…' : '拒绝申请'}</Button><Button primary onClick={() => decide('APPROVED')}>{pending ? '处理中…' : '批准申请'}</Button></div><p className="warning"><AlertTriangle size={15}/>批准不会在当前页面直接执行退款，后续处理由 Outbox 和消息消费者完成。</p></> : <p>选择一条审批申请查看详情。</p>}</aside></div></>;
}

const approvalActionLabel = (actionType) => ({'refund.request':'申请退款','compensation.issue':'发放补偿'})[actionType] || actionType;
const approvalStatusLabel = (status) => ({PENDING:'待审批',APPROVED:'已批准',REJECTED:'已拒绝',EXPIRED:'已过期',EXECUTING:'执行中',EXECUTED:'已执行',FAILED:'执行失败'})[status] || status;
const approvalStatusClass = (status) => status === 'APPROVED' || status === 'EXECUTED' ? 'success' : status === 'PENDING' || status === 'EXECUTING' ? 'processing' : 'danger';
const formatDateTime = (value) => value ? new Intl.DateTimeFormat('zh-CN', {dateStyle:'short', timeStyle:'short'}).format(new Date(value)) : '—';

const PageHeader=({title,sub,children})=><div className="page-header"><div><h1>{title}</h1>{sub&&<p>{sub}</p>}</div><div className="header-actions">{children}</div></div>;
const Button=({children,primary,onClick,icon:Icon,disabled=false})=><button onClick={onClick} disabled={disabled} className={primary?'btn primary':'btn'}>{Icon&&<Icon size={16}/>} {children}</button>;
const Stat=({label,value,delta,tone=''})=><div className="stat"><span>{label}</span><strong className={tone}>{value}</strong><small>{delta}</small></div>;
function Overview({onNav,overview,tickets:workspaceTickets}){const metrics=overview||{completedGenerations:1284,handoffGenerations:86,aiResolutionRate:.942,overdueTickets:7,inputTokens:0,outputTokens:0,averageGenerationLatencyMs:0};return <><PageHeader title="工作台总览" sub="实时掌握客服、知识库和 SLA 运行情况"><Button>今日 · 2026年8月9日 <ChevronDown size={14}/></Button><Button icon={ExternalLink}>导出报告</Button></PageHeader><div className="stats"><Stat label="AI 已解决" value={metrics.completedGenerations.toLocaleString()} delta={`转人工 ${metrics.handoffGenerations.toLocaleString()} 次`}/><Stat label="AI 解决率" value={`${(metrics.aiResolutionRate*100).toFixed(1)}%`} delta="按已完成生成统计" tone="warn"/><Stat label="模型 Token" value={(metrics.inputTokens+metrics.outputTokens).toLocaleString()} delta={`平均延迟 ${metrics.averageGenerationLatencyMs} ms`}/><Stat label="SLA 风险" value={metrics.overdueTickets.toLocaleString()} delta="仍未解决的逾期工单" tone="danger"/></div><div className="grid two"><section className="panel chart-panel"><div className="panel-head"><h2>客服会话趋势</h2><div className="legend"><i className="cyan"/>AI 自动处理 <i className="violet"/>转人工</div></div><div className="chart"><div className="chart-grid"/><svg viewBox="0 0 600 210" preserveAspectRatio="none"><polyline points="0,150 70,122 140,138 210,72 280,94 350,55 420,82 490,32 560,50 600,20" fill="none" stroke="#20b9d8" strokeWidth="4"/><polyline points="0,188 70,166 140,180 210,142 280,156 350,132 420,145 490,110 560,122 600,102" fill="none" stroke="#7564ee" strokeWidth="4"/></svg><div className="axis"><span>周一</span><span>周二</span><span>周三</span><span>周四</span><span>周五</span><span>周六</span><span>周日</span></div></div></section><section className="panel"><div className="panel-head"><h2>SLA 风险工单</h2><button className="text-link" onClick={()=>onNav('tickets')}>查看全部 <ArrowRight size={14}/></button></div>{workspaceTickets.slice(0,3).map(t=><div className="risk-row" key={t.id}><div><strong>{t.id}</strong><span>{t.title}</span></div><em className={t.priority==='紧急'?'danger':''}>{t.priority}</em><small>{t.sla}</small></div>)}</section></div><div className="grid three"><section className="panel"><div className="panel-head"><h2>知识库健康度</h2><button className="text-link" onClick={()=>onNav('knowledge')}>管理知识库</button></div><div className="health-big"><CheckCircle2/><strong>健康</strong><span>248 份文档 · 1,240 个切片</span></div><div className="progress large"><span style={{width:'92%'}}/></div><div className="split-note"><span>已索引 <b>244</b></span><span>处理中 <b>3</b></span><span>失败 <b className="danger">1</b></span></div></section><section className="panel"><div className="panel-head"><h2>RAG 检索质量</h2><SlidersHorizontal size={17}/></div><div className="quality"><div><strong>0.86</strong><span>平均相关性</span></div><div><strong>94.2%</strong><span>引用覆盖率</span></div><div><strong>3.8%</strong><span>无证据回答率</span></div></div></section><section className="panel"><div className="panel-head"><h2>最近活动</h2><button className="text-link">查看日志</button></div><Activity text="退款与退货政策已重新索引" time="2 分钟前" icon={FileText}/><Activity text="TKT-52418 已分配给坐席 A" time="12 分钟前" icon={Ticket}/><Activity text="退款审批申请待处理" time="26 分钟前" icon={ShieldCheck}/></section></div></>}
function Activity({text,time,icon:Icon}){return <div className="activity"><span className="activity-icon"><Icon size={15}/></span><div><strong>{text}</strong><small>{time}</small></div></div>}
function Customer(){const [orders,setOrders]=useState([]);const [selectedOrder,setSelectedOrder]=useState(null);const [error,setError]=useState('');const [message,setMessage]=useState('');const [messages,setMessages]=useState([]);const [generating,setGenerating]=useState(false);const conversationId=useRef(null);useEffect(()=>{getCustomerOrders().then(items=>{setOrders(items);setSelectedOrder(items[0]||null);}).catch(loadError=>setError(loadError.message));},[]);const poll=async generationId=>{let lastEventId;for(let attempt=0;attempt<40;attempt++){const events=await readGenerationEvents(generationId,lastEventId);for(const event of events){lastEventId=event.id||lastEventId;if(event.type==='text.delta')setMessages(items=>{const last=items.at(-1);return last?.role==='assistant'?[...items.slice(0,-1),{...last,content:last.content+event.data.text}]:[...items,{role:'assistant',content:event.data.text||''}];});if(event.type==='handoff.required')setMessages(items=>[...items,{role:'system',content:'已转人工客服，坐席会继续处理该问题。'}]);if(event.type==='model.completed'||event.type==='handoff.required')return;}await new Promise(resolve=>setTimeout(resolve,350));}throw new Error('生成进度暂未完成，请稍后重试。');};const send=async event=>{event.preventDefault();const content=message.trim();if(!content||generating)return;setError('');setGenerating(true);setMessages(items=>[...items,{role:'customer',content}]);setMessage('');try{if(!conversationId.current)conversationId.current=(await createConversation()).id;const generation=await submitCustomerMessage(conversationId.current,content,crypto.randomUUID());await poll(generation.id);}catch(sendError){setError(sendError.message);}finally{setGenerating(false);}};return <><PageHeader title="我的订单与服务" sub="查看属于当前账户的订单，并通过 AI 与坐席协同获得支持"><Button>帮助中心</Button></PageHeader><div className="customer-layout"><section className="panel customer-tickets"><h2>我的订单</h2>{orders.map(order=><button className={'customer-ticket '+(selectedOrder?.orderNo===order.orderNo?'selected':'')} key={order.orderNo} onClick={()=>setSelectedOrder(order)}><strong>{order.orderNo}</strong><span>{order.status}</span><p>{currencyAmount(order.totalAmount,order.currency)}</p><small>下单时间：{formatDateTime(order.createdAt)}</small></button>)}{!orders.length&&!error&&<p className="empty-state">正在加载订单…</p>}{error&&<p className="warning">{error}</p>}</section><section className="panel customer-detail"><div className="detail-head"><div><span className="eyebrow">客服会话</span><h2>{selectedOrder?`订单 ${selectedOrder.orderNo} 的服务咨询`:'选择一个订单开始咨询'}</h2><small>消息采用独立生成任务，网络中断后可从最后事件继续读取。</small></div><span className={'status '+(generating?'processing':'success')}>{generating?'AI 正在处理':'账户已验证'}</span></div><div className="conversation-body">{!messages.length&&<div className="customer-message"><strong>下一步</strong><p>提交订单问题后，系统会检索租户知识库；证据不足、模型失败或高风险动作会自动转人工。</p></div>}{messages.map((item,index)=><div className={'message '+(item.role==='assistant'?'ai':item.role==='system'?'note':'customer')} key={index}><span className="message-avatar">{item.role==='assistant'?<Bot size={17}/>:item.role==='system'?'内':'客'}</span><div><small>{item.role==='assistant'?'SupportFlow AI':item.role==='system'?'服务状态':'我'}</small><p>{item.content}</p></div></div>)}</div><form className="composer" onSubmit={send}><textarea value={message} onChange={event=>setMessage(event.target.value)} placeholder={selectedOrder?'描述订单问题…':'请先选择订单'} disabled={!selectedOrder||generating}/><div className="customer-actions"><Button primary icon={Send}>{generating?'生成中…':'发送消息'}</Button></div></form><p className="safe-note"><ShieldCheck size={15}/>退款和补偿必须经过人工审批，系统不会在会话中直接执行资金操作。</p></section></div></>}

const currencyAmount=(amount,currency)=>new Intl.NumberFormat('zh-CN',{style:'currency',currency:currency||'CNY'}).format(Number(amount));
function Tickets({tickets:workspaceTickets,selected,setSelected,setWorkspaceTickets,notice,setNotice}) {
  const [comments,setComments] = useState([]);
  const [comment,setComment] = useState('');
  const [pending,setPending] = useState(false);
  useEffect(() => {
    if (!selected?.rawId) return;
    getTicketComments(selected.rawId).then(setComments).catch(error => setNotice(error.message));
  }, [selected?.rawId, setNotice]);
  const updateTicket = updated => {
    const normalized = toWorkspaceTicket(updated);
    setWorkspaceTickets(items => items.map(item => item.rawId === normalized.rawId ? normalized : item));
    setSelected(normalized);
  };
  const act = async (action, success) => {
    if (!selected || pending) return;
    setPending(true);
    try {
      updateTicket(await action(selected.rawId));
      setNotice(success);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setPending(false);
    }
  };
  const sendComment = async () => {
    const content = comment.trim();
    if (!content || !selected || pending) return;
    setPending(true);
    try {
      const added = await addTicketComment(selected.rawId, content);
      setComments(items => [...items, added]);
      setComment('');
      setNotice('内部备注已保存。');
    } catch (error) {
      setNotice(error.message);
    } finally {
      setPending(false);
    }
  };
  if (!selected) return <><PageHeader title="工单协同" sub="当前没有可处理工单"/><p className="empty-state">当前没有工单。</p></>;
  const canClaim = !selected.assignedMembershipId && selected.statusCode === 'NEW';
  const canResolve = selected.statusCode === 'OPEN' || selected.statusCode === 'PENDING_CUSTOMER' || selected.statusCode === 'PENDING_APPROVAL';
  const canClose = selected.statusCode === 'RESOLVED';
  return <><PageHeader title="工单协同" sub={`我的工单 · ${workspaceTickets.length} 个待处理`}><Button icon={Plus} primary onClick={()=>setNotice('新建工单面板尚未接入。')}>新建工单</Button></PageHeader><div className="ticket-layout">
    <section className="panel ticket-list"><div className="tabs compact"><button className="selected">全部工单 <b>{workspaceTickets.length}</b></button><button>未分配</button><button>高优先级</button></div>{workspaceTickets.map(t=><button className={'ticket-item '+(selected.id===t.id?'selected':'')} key={t.id} onClick={()=>setSelected(t)}><div className="ticket-top"><strong>{t.id}</strong><span className={'priority '+(t.priority==='紧急'?'danger':'')}>{t.priority}</span></div><p>{t.title}</p><small>{t.customer} · {t.sla}</small></button>)}</section>
    <section className="panel conversation"><div className="conversation-head"><div><h2>{selected.title}</h2><span>{selected.id} · {selected.status} · 优先级 {selected.priority}</span></div><span className="sla-badge"><Clock3 size={15}/> {selected.sla}</span></div>
      <div className="conversation-body"><div className="message customer"><span className="message-avatar">客</span><div><small>{selected.customer}</small><p>该会话已转交人工坐席处理，请结合订单与知识库证据回复客户。</p></div></div>{comments.map(item=><div className="message note" key={item.id}><span className="message-avatar">内</span><div><small>坐席备注 · {formatDateTime(item.createdAt)}</small><p>{item.content}</p></div></div>)}{!comments.length&&<p className="empty-state">暂时没有内部备注。</p>}</div>
      <div className="composer"><div className="composer-tabs"><button className="selected">内部备注</button><button className="ai-link" onClick={()=>setNotice('请在审核过知识库证据后编辑回复。')}><Bot size={15}/> 回复建议</button></div><textarea aria-label="内部备注" value={comment} onChange={event=>setComment(event.target.value)} placeholder="记录坐席处理信息…" disabled={pending}/><div className="composer-actions">{canClaim&&<Button primary onClick={()=>act(claimTicket,'工单已认领，现可继续处理。')}>{pending?'处理中…':'认领工单'}</Button>}<Button primary icon={Send} onClick={sendComment} disabled={pending}>{pending?'处理中…':'保存内部备注'}</Button>{canResolve&&<Button onClick={()=>act(ticketId=>changeTicketStatus(ticketId,'RESOLVED'),'工单已标记为已解决。')}>标记已解决</Button>}{canClose&&<Button onClick={()=>act(ticketId=>changeTicketStatus(ticketId,'CLOSED'),'工单已关闭。')}>关闭工单</Button>}</div></div>
    </section>
    <aside className="panel context-panel"><h2>客户与订单</h2><div className="profile"><div className="profile-avatar">客</div><div><strong>{selected.customer}</strong><small>消费者服务工单</small></div></div><div className="context-block"><span>工单状态</span><strong>{selected.status}</strong><small>{selected.assignedMembershipId?'已分配给坐席':'等待坐席认领'}</small></div><h3>处理提示</h3><div className="evidence-line"><CheckCircle2/>先核对订单与知识库依据</div><div className="evidence-line"><CheckCircle2/>退款与补偿仍需走审批流程</div><Button icon={RefreshCcw} onClick={()=>getTicketComments(selected.rawId).then(setComments).then(()=>setNotice('内部备注已刷新。')).catch(error=>setNotice(error.message))}>刷新处理记录</Button></aside>
  </div></>;
}
