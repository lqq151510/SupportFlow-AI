const baseUrl = process.env.SUPPORTFLOW_BASE_URL || 'http://127.0.0.1:8080';
const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
const tenantCode = `perf-${suffix}`;
const password = 'performance-test-only-123';
const adminEmail = `admin-${suffix}@supportflow.test`;
const customerEmail = `customer-${suffix}@supportflow.test`;

async function request(path, {method = 'GET', token, body, expected = 200} = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      ...(token ? {Authorization: `Bearer ${token}`} : {}),
      ...(body ? {'Content-Type': 'application/json'} : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  if (response.status !== expected) {
    throw new Error(`${method} ${path} returned ${response.status}: ${text}`);
  }
  if (response.status === 204 || text.length === 0) return null;
  return JSON.parse(text);
}

await request('/api/v1/tenants/register', {
  method: 'POST', expected: 201,
  body: {tenantCode, tenantName: 'Performance Test Shop', email: adminEmail, displayName: 'Performance Admin', password},
});
await request('/api/v1/customers/register', {
  method: 'POST', expected: 201,
  body: {tenantCode, email: customerEmail, displayName: 'Performance Customer', password},
});
const admin = await request('/api/v1/auth/login', {method: 'POST', body: {tenantCode, email: adminEmail, password}});
const customer = await request('/api/v1/auth/login', {method: 'POST', body: {tenantCode, email: customerEmail, password}});
const knowledgeBase = await request('/api/v1/admin/knowledge-bases', {
  method: 'POST', token: admin.accessToken, expected: 201,
  body: {name: 'Performance Policies', description: 'Deterministic Mock Model load-test knowledge'},
});
const document = await request(`/api/v1/admin/knowledge-bases/${knowledgeBase.id}/documents`, {
  method: 'POST', token: admin.accessToken, expected: 201,
  body: {fileName: 'orders.txt', content: '订单状态可以通过订单列表查询。发货后的订单会显示物流信息。'},
});
await request(`/api/v1/admin/knowledge-bases/${knowledgeBase.id}/documents/${document.id}/index`, {
  method: 'POST', token: admin.accessToken,
});
const conversation = await request('/api/v1/customer/conversations', {
  method: 'POST', token: customer.accessToken, expected: 201,
});

process.stdout.write(JSON.stringify({
  baseUrl,
  accessToken: customer.accessToken,
  conversationId: conversation.id,
}));
