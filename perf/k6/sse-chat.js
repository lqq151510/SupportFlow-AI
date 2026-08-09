import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = __ENV.SUPPORTFLOW_BASE_URL || 'http://localhost:8080';
const token = __ENV.SUPPORTFLOW_ACCESS_TOKEN;
const conversationId = __ENV.SUPPORTFLOW_CONVERSATION_ID;

if (!token || !conversationId) {
  throw new Error('SUPPORTFLOW_ACCESS_TOKEN and SUPPORTFLOW_CONVERSATION_ID are required');
}

export const options = {
  scenarios: {
    sse_chat: {
      executor: 'constant-vus',
      vus: Number(__ENV.K6_VUS || 100),
      duration: __ENV.K6_DURATION || '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{operation:sse_connect}': ['p(95)<1000'],
  },
};

const headers = {
  Authorization: `Bearer ${token}`,
  'Content-Type': 'application/json',
};

export default function () {
  const key = `k6-${__VU}-${__ITER}`;
  const created = http.post(
    `${baseUrl}/api/v1/customer/conversations/${conversationId}/messages`,
    JSON.stringify({ content: '请查询订单状态' }),
    { headers: { ...headers, 'Idempotency-Key': key }, tags: { operation: 'message_submit' } },
  );
  check(created, { 'message accepted': (response) => response.status === 202 });
  if (created.status !== 202) return;

  const generationId = created.json('id');
  const events = http.get(
    `${baseUrl}/api/v1/customer/generations/${generationId}/events`,
    { headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' }, tags: { operation: 'sse_connect' }, timeout: '5s' },
  );
  check(events, { 'SSE connected': (response) => response.status === 200 });
  sleep(1);
}
