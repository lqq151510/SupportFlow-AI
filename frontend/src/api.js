const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

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

export async function getSession() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('未登录');
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/session`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('登录已失效');
  return response.json();
}

export async function getCustomerOrders() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以查看订单');
  const response = await fetch(`${API_BASE_URL}/api/v1/customer/orders`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`订单加载失败 (${response.status})`);
  return response.json();
}
