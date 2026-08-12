import http from 'k6/http';
import {check} from 'k6';

const baseUrl = __ENV.SUPPORTFLOW_BASE_URL || 'http://127.0.0.1:8080';
const token = __ENV.SUPPORTFLOW_ACCESS_TOKEN;

if (!token) throw new Error('SUPPORTFLOW_ACCESS_TOKEN is required');

export const options = {
  scenarios: {
    customer_orders: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.K6_RATE || 100),
      timeUnit: '1s',
      duration: __ENV.K6_DURATION || '30s',
      preAllocatedVUs: Number(__ENV.K6_PREALLOCATED_VUS || 50),
      maxVUs: Number(__ENV.K6_MAX_VUS || 200),
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{operation:orders_list}': ['p(95)<300'],
  },
};

export default function () {
  const response = http.get(`${baseUrl}/api/v1/customer/orders`, {
    headers: {Authorization: `Bearer ${token}`},
    tags: {operation: 'orders_list'},
  });
  check(response, {'orders returned': (result) => result.status === 200});
}
