const isDesktop = typeof window !== 'undefined' && (Boolean(window.__TAURI_INTERNALS__) || Boolean(window.__TAURI__));
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || (isDesktop ? 'http://localhost:8080' : (import.meta.env.PROD ? '' : 'http://localhost:8080'));

export async function getBackendHealth() {
  const response = await fetch(`${API_BASE_URL}/actuator/health`);
  if (!response.ok) throw new Error(`本地服务健康检查失败 (${response.status})`);
  const health = await response.json();
  if (health.status !== 'UP') throw new Error('本地服务尚未就绪');
  return health;
}

function accessToken(message) {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error(message);
  return token;
}

async function adminRequest(path, options = {}, errorLabel = '请求失败') {
  const token = accessToken('请先登录管理工作台');
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {Authorization: `Bearer ${token}`, ...options.headers},
  });
  if (!response.ok) throw new Error(`${errorLabel} (${response.status})`);
  return response.status === 204 ? null : response.json();
}

export async function getOperationsOverview() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以查看运营数据');
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/operations/overview`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`运营数据加载失败 (${response.status})`);
  return response.json();
}

export async function getTickets() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以查看工单');
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/tickets`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`工单加载失败 (${response.status})`);
  return response.json();
}

export const getKnowledgeBases = () => adminRequest('/api/v1/admin/knowledge-bases', {}, '知识库加载失败');
export const createKnowledgeBase = values => adminRequest('/api/v1/admin/knowledge-bases', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values),
}, '知识库创建失败');
export const getKnowledgeDocuments = knowledgeBaseId => adminRequest(`/api/v1/admin/knowledge-bases/${knowledgeBaseId}/documents`, {}, '文档加载失败');
export const uploadKnowledgeDocument = (knowledgeBaseId, file) => {
  const body = new FormData();
  body.append('file', file);
  return adminRequest(`/api/v1/admin/knowledge-bases/${knowledgeBaseId}/documents/upload`, {method: 'POST', body}, '文档上传失败');
};

export const getModelConfigs = () => adminRequest('/api/v1/admin/models', {}, '模型配置加载失败');
export const getAssignableMembers = () => adminRequest('/api/v1/admin/members', {}, '坐席列表加载失败');
export const createModelConfig = values => adminRequest('/api/v1/admin/models', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values),
}, '模型配置保存失败');
export const updateModelConfig = (modelConfigId, values) => adminRequest(`/api/v1/admin/models/${modelConfigId}`, {
  method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values),
}, '模型配置更新失败');
export const setDefaultModelConfig = modelConfigId => adminRequest(`/api/v1/admin/models/${modelConfigId}/default`, {
  method: 'PATCH',
}, '默认模型切换失败');
export const setKnowledgeDefaultModelConfig = modelConfigId => adminRequest(`/api/v1/admin/models/${modelConfigId}/knowledge-default`, {
  method: 'PATCH',
}, '知识整理模型切换失败');
export const probeModelConnection = ({baseUrl, apiKey}) => adminRequest('/api/v1/admin/models/probe', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({baseUrl, apiKey}),
}, '模型连接探测失败');
export const getModelUsageOverview = () => adminRequest('/api/v1/admin/models/usage/overview', {}, '模型用量加载失败');
export const getRecentModelUsages = (limit = 15) => adminRequest(`/api/v1/admin/models/usage/recent?limit=${limit}`, {}, '调用明细加载失败');
export const organizeKnowledgeDocument = (knowledgeBaseId, documentId) => adminRequest(`/api/v1/admin/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/organize`, {
  method: 'POST',
}, '文档智能整理失败');

async function ticketRequest(ticketId, suffix, options = {}) {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以处理工单');
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/tickets/${ticketId}${suffix}`, {
    ...options,
    headers: {Authorization: `Bearer ${token}`, ...(options.body ? {'Content-Type': 'application/json'} : {}), ...options.headers},
  });
  if (!response.ok) throw new Error(`工单操作失败 (${response.status})`);
  return response.json();
}

export const claimTicket = (ticketId, idempotencyKey) => ticketRequest(ticketId, '/claim', {
  method: 'POST', headers: {'Idempotency-Key': idempotencyKey},
});
export const assignTicket = (ticketId, membershipId) => ticketRequest(ticketId, '/assign', {
  method: 'POST', body: JSON.stringify({membershipId}),
});
export const changeTicketStatus = (ticketId, status) => ticketRequest(ticketId, '/status', {method: 'POST', body: JSON.stringify({status})});
export const getTicketComments = ticketId => ticketRequest(ticketId, '/comments');
export const getTicketContext = ticketId => ticketRequest(ticketId, '/context');
export const addTicketComment = (ticketId, content) => ticketRequest(ticketId, '/comments', {method: 'POST', body: JSON.stringify({content})});

export async function getApprovals() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以查看审批');
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/approvals`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`审批列表加载失败 (${response.status})`);
  return response.json();
}

export async function decideApproval(approvalId, decision, idempotencyKey = crypto.randomUUID()) {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以处理审批');
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/approvals/${approvalId}/decision`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Idempotency-Key': `approval-${approvalId}-${decision.toLowerCase()}-${idempotencyKey}`,
    },
    body: JSON.stringify({ decision }),
  });
  if (!response.ok) throw new Error(`审批处理失败 (${response.status})`);
  return response.json();
}

export async function login({ tenantCode, email, password }) {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tenantCode, email, password }),
  });
  if (!response.ok) throw new Error('登录失败，请检查租户代码、邮箱和密码');
  return response.json();
}

async function registrationError(response, fallback) {
  const problem = await response.json().catch(() => null);
  switch (problem?.detail) {
    case 'tenant code does not exist':
      return '租户代码不存在。请先创建工作区，或向管理员确认租户代码。';
    case 'tenant code already exists':
      return '租户代码已存在，请改用其他代码或直接登录。';
    case 'email already exists':
      return '该邮箱已注册，请返回登录或改用其他邮箱。';
    default:
      return fallback;
  }
}

export async function registerTenant({ email, displayName, password }) {
  const response = await fetch(`${API_BASE_URL}/api/v1/tenants/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, displayName, password }),
  });
  if (!response.ok) throw new Error(await registrationError(response, '工作区创建失败，请检查填写内容后重试。'));
  return response.json();
}

export async function registerCustomer({ tenantCode, email, displayName, password }) {
  const response = await fetch(`${API_BASE_URL}/api/v1/customers/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tenantCode, email, displayName, password }),
  });
  if (!response.ok) throw new Error(await registrationError(response, '消费者注册失败，请检查填写内容后重试。'));
  return response.json();
}

export async function getSession() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('未登录');
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/session`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('登录已失效');
  return response.json();
}

export const getMyProfile = () => adminRequest('/api/v1/auth/profile', {}, '个人资料加载失败');
export const updateMyProfile = values => adminRequest('/api/v1/auth/profile', {
  method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values),
}, '个人资料保存失败');
export const changePassword = ({currentPassword, newPassword}) => adminRequest('/api/v1/auth/change-password', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({currentPassword, newPassword}),
}, '密码更新失败');

export async function getCustomerOrders() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以查看订单');
  const response = await fetch(`${API_BASE_URL}/api/v1/customer/orders`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`订单加载失败 (${response.status})`);
  return response.json();
}

export async function createConversation() {
  const token = localStorage.getItem('supportflow.accessToken');
  const response = await fetch(`${API_BASE_URL}/api/v1/customer/conversations`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`会话创建失败 (${response.status})`);
  return response.json();
}

export async function submitCustomerMessage(conversationId, content, idempotencyKey) {
  const token = localStorage.getItem('supportflow.accessToken');
  const response = await fetch(`${API_BASE_URL}/api/v1/customer/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) throw new Error(`消息提交失败 (${response.status})`);
  return response.json();
}

export async function readGenerationEvents(generationId, lastEventId) {
  const token = localStorage.getItem('supportflow.accessToken');
  const response = await fetch(`${API_BASE_URL}/api/v1/customer/generations/${generationId}/events`, {
    headers: { Authorization: `Bearer ${token}`, ...(lastEventId ? {'Last-Event-ID': lastEventId} : {}) },
  });
  if (!response.ok) throw new Error(`生成事件读取失败 (${response.status})`);
  return parseSse(await response.text());
}

function parseSse(payload) {
  return payload.trim().split(/\r?\n\r?\n/).filter(Boolean).map(block => {
    const fields = Object.fromEntries(block.split(/\r?\n/).map(line => {
      const divider = line.indexOf(':');
      return divider < 0 ? [line, ''] : [line.slice(0, divider), line.slice(divider + 1).trimStart()];
    }));
    return {id: fields.id, type: fields.event, data: JSON.parse(fields.data || '{}')};
  });
}
