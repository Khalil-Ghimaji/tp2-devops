import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
// Part du trafic envoyée sur /flaky. 0.05 par défaut ; 0.30 pour déclencher les alertes burn-rate.
const FLAKY_SHARE = parseFloat(__ENV.FLAKY_SHARE || '0.05');

export const options = {
  scenarios: {
    ramp_up: {                       // 0 -> 100 VU
      executor: 'ramping-vus', startVUs: 0, exec: 'mixed',
      stages: [{ duration: '2m', target: 100 }, { duration: '1m', target: 100 }, { duration: '30s', target: 0 }],
    },
    stress_500: {                    // palier prolongé à 500 VU
      executor: 'ramping-vus', startVUs: 0, exec: 'mixed', startTime: '4m',
      stages: [{ duration: '1m', target: 500 }, { duration: '5m', target: 500 }, { duration: '30s', target: 0 }],
    },
    spike_1500: {                    // pic brutal à 1500 VU pendant 30 s
      executor: 'ramping-vus', startVUs: 0, exec: 'mixed', startTime: '11m',
      stages: [{ duration: '5s', target: 1500 }, { duration: '30s', target: 1500 }, { duration: '5s', target: 0 }],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.005'],        // SLO dispo 99.5 %
    http_req_duration: ['p(95)<200'],       // SLO latence p95 <= 200 ms
  },
};

export function mixed() {
  const r = Math.random();
  let res;
  if (r < FLAKY_SHARE) {
    res = http.get(`${BASE}/flaky`, { tags: { name: 'flaky' } });
  } else if (r < FLAKY_SHARE + 0.3) {
    res = http.post(`${BASE}/checkout`, JSON.stringify({ product_id: 1 + Math.floor(Math.random() * 3), quantity: 1 }),
      { headers: { 'Content-Type': 'application/json' }, tags: { name: 'checkout' } });
  } else {
    res = http.get(`${BASE}/products`, { tags: { name: 'products' } });
  }
  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(0.1);
}
