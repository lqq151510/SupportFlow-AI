// 展示层共享的标签与格式化工具。
// React 版本把这些 helper 散落在 App.jsx / AccountCenter.jsx 内，移植时收敛到这里，
// 保证同一业务值在工单、审批、个人中心三处渲染一致。

export const roleLabel = {
  TENANT_ADMIN: '工作区管理员',
  SUPERVISOR: '客服主管',
  AGENT: '客服坐席',
  CUSTOMER: '消费者',
};

export const scenarioLabel = {
  CHAT: '客服智能会话',
  KNOWLEDGE_ORGANIZATION: '知识库自动整理',
  ASSISTANT: '智能助手问答',
  PROBE: '连接探测测试',
};

export const priorityLabel = priority => ({LOW: '低', NORMAL: '普通', HIGH: '高', URGENT: '紧急'})[priority] || priority;

export const statusLabel = status => ({NEW: '待处理', OPEN: '处理中', PENDING_CUSTOMER: '等待客户', PENDING_APPROVAL: '待审批', RESOLVED: '已解决', CLOSED: '已关闭'})[status] || status;

export const slaLabel = dueAt => {
  const minutes = Math.round((new Date(dueAt).getTime() - Date.now()) / 60000);
  return minutes < 0 ? `已超时 ${Math.abs(minutes)} 分钟` : `剩余 ${minutes} 分钟`;
};

export const toWorkspaceTicket = ticket => ({
  rawId: ticket.id,
  id: `TKT-${ticket.id}`,
  title: ticket.title,
  customer: `客户 #${ticket.customerId}`,
  priority: priorityLabel(ticket.priority),
  status: statusLabel(ticket.status),
  statusCode: ticket.status,
  assignedMembershipId: ticket.assignedMembershipId,
  sla: slaLabel(ticket.resolutionDueAt),
});

export const approvalActionLabel = actionType => ({'refund.request': '申请退款', 'compensation.issue': '发放补偿'})[actionType] || actionType;

export const approvalStatusLabel = status => ({PENDING: '待审批', APPROVED: '已批准', REJECTED: '已拒绝', REVOKED: '已撤销', EXPIRED: '已过期', EXECUTING: '执行中', EXECUTED: '已执行', FAILED: '执行失败'})[status] || status;

export const approvalStatusClass = status => (status === 'APPROVED' || status === 'EXECUTED' ? 'success' : status === 'PENDING' || status === 'EXECUTING' ? 'processing' : 'danger');

export const formatDateTime = value => (value ? new Intl.DateTimeFormat('zh-CN', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(value)) : '—');

export const formatJoinedAt = value => (value ? new Intl.DateTimeFormat('zh-CN', {year: 'numeric', month: 'long', day: 'numeric'}).format(new Date(value)) : '—');

export const formatTime = value => (value ? new Intl.DateTimeFormat('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'}).format(new Date(value)) : '—');

export const currencyAmount = (amount, currency) => new Intl.NumberFormat('zh-CN', {style: 'currency', currency: currency || 'CNY'}).format(Number(amount));

export const initials = name => (name || 'U').trim().slice(0, 2).toLocaleUpperCase();
