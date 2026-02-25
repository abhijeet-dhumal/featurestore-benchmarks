# Feast Benchmark Report - SQLITE

**Generated:** 2026-02-25 15:01:42  
**Feast Version:** 0.60.0  
**Online Store:** sqlite  
**SLA Target:** 60ms p99

## Summary

- **Total Tests:** 15
- **SLA Pass Rate:** 86.7%

---

## Latency Matrix (Features × Entities)

| Features | Entities | p50 (ms) | p95 (ms) | p99 (ms) | SLA | Breakdown |
|----------|----------|----------|----------|----------|-----|-----------|
| 50 | 1 | 1.6 | 1.7 | 1.7 | ✅ | read=1% proto=2% |
| 50 | 10 | 2.8 | 2.8 | 2.8 | ✅ | read=4% proto=7% |

---

## Feature View Scaling

| FVs | Total Features | Entities | p99 (ms) | SLA |
|-----|----------------|----------|----------|-----|
| 1 | 10 | 100 | 9.4 | ✅ |
| 10 | 100 | 100 | 44.2 | ✅ |
| 50 | 500 | 100 | 181.7 | ❌ |
| 100 | 1000 | 100 | 363.5 | ❌ |

---

## Transformation Overhead

| Mode | Entities | p50 (ms) | p99 (ms) | SLA |
|------|----------|----------|----------|-----|
| NONE | 1 | 1.5 | 1.6 | ✅ |
| PYTHON | 1 | 2.0 | 2.3 | ✅ |
| PANDAS | 1 | 2.2 | 2.2 | ✅ |
| NONE | 10 | 2.7 | 2.8 | ✅ |
| PYTHON | 10 | 3.3 | 3.6 | ✅ |
| PANDAS | 10 | 3.5 | 3.6 | ✅ |
| NONE | 100 | 14.9 | 17.1 | ✅ |
| PYTHON | 100 | 17.1 | 17.2 | ✅ |
| PANDAS | 100 | 17.5 | 17.7 | ✅ |

---

## Throughput

| Workers | RPS | RPH | Target (3M) | Avg Latency | p99 Latency |
|---------|-----|-----|-------------|-------------|-------------|
| 1 | 365.4 | 1,315,440 | 43.8% | 2.7ms | 3.1ms |
| 5 | 231.7 | 834,120 | 27.8% | 21.6ms | 55.4ms |
| 10 | 239.6 | 862,560 | 28.8% | 41.9ms | 136.8ms |

---

## Key Findings

- **Worst case latency:** 2.8ms at 50f × 10e
- **FV scaling impact:** 100 FVs → 363.5ms p99
- **Peak throughput:** 1,315,440 RPH (43.8% of 3M target)
