import http from 'k6/http';
import { check, sleep, group } from 'k6';

const BASE_URL = __ENV.TARGET_URL || 'http://127.0.0.1:7000';

export const options = {
  stages: [
    { duration: '10s', target: 5 },   // Ramp up
    { duration: '30s', target: 5 },   // Steady load
    { duration: '10s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'],   // 95% of requests < 5s
    http_req_failed: ['rate<0.05'],       // < 5% errors
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

export default function () {
  group('Health Check', () => {
    const res = http.get(`${BASE_URL}/api/health`);
    check(res, {
      'status 200': (r) => r.status === 200,
      'healthy response': (r) => r.json().status === 'healthy',
    });
  });

  group('Knowledge Status', () => {
    const res = http.get(`${BASE_URL}/api/knowledge/status`);
    check(res, {
      'status 200': (r) => r.status === 200,
      'trinite present': (r) => r.json().trinite !== undefined,
    });
  });

  group('Agent List', () => {
    const res = http.get(`${BASE_URL}/api/agents`);
    check(res, {
      'status 200': (r) => r.status === 200,
      'agents array': (r) => Array.isArray(r.json().agents),
    });
  });

  group('Memory Search', () => {
    const payload = JSON.stringify({ query: 'test' });
    const params = { headers: { 'Content-Type': 'application/json' } };
    const res = http.post(`${BASE_URL}/api/memory/search`, payload, params);
    check(res, {
      'memory endpoint responsive': (r) => r.status === 200 || r.status === 422,
    });
  });

  group('Observer Drift', () => {
    const res = http.get(`${BASE_URL}/api/observer/drift`);
    check(res, {
      'status 200': (r) => r.status === 200,
      'drift level present': (r) => r.json().drift_level !== undefined,
    });
  });

  sleep(1);
}

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    target: BASE_URL,
    metrics: {
      total_requests: data.metrics.http_reqs?.values?.count || 0,
      failed_requests: data.metrics.http_req_failed?.values?.rate || 0,
      p95_latency_ms: data.metrics.http_req_duration?.values?.['p(95)'] || 0,
      avg_latency_ms: data.metrics.http_req_duration?.values?.avg || 0,
      max_latency_ms: data.metrics.http_req_duration?.values?.max || 0,
    },
    checks: {
      passed: data.root_group?.checks?.filter(c => c.passes > 0).length || 0,
      total: data.root_group?.checks?.length || 0,
    },
  };

  return {
    'stdout': JSON.stringify(summary, null, 2),
    'data/load-test-report.json': JSON.stringify(summary, null, 2),
  };
}
