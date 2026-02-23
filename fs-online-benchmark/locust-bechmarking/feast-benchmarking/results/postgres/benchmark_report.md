# Feast Benchmark Report - POSTGRES

**Generated:** 2026-02-23 21:49:26  
**Feast Version:** 0.60.0  
**Online Store:** postgres  
**SLA Target:** 60ms p99

## Summary

- **Total Tests:** 4
- **SLA Pass Rate:** 0.0%

---

## Latency Matrix (Features × Entities)

| Features | Entities | p50 (ms) | p95 (ms) | p99 (ms) | SLA | Breakdown |
|----------|----------|----------|----------|----------|-----|-----------|
| 50 | 1 | 200.4 | 333.5 | 333.5 | ❌ | read=94% proto=0% |
| 50 | 10 | 184.9 | 203.4 | 203.4 | ❌ | read=94% proto=1% |
| 50 | 100 | 1410.7 | 2354.1 | 2354.1 | ❌ | read=98% proto=1% |

---

## Feature View Scaling

| FVs | Total Features | Entities | p99 (ms) | SLA |
|-----|----------------|----------|----------|-----|
| 1 | 10 | 100 | 377.3 | ❌ |

---

## Transformation Overhead

| Mode | Entities | p50 (ms) | p99 (ms) | SLA |
|------|----------|----------|----------|-----|

---

## Throughput

| Workers | RPS | RPH | Target (3M) | Avg Latency | p99 Latency |
|---------|-----|-----|-------------|-------------|-------------|
| 1 | 1.4 | 5,040 | 0.2% | 789.6ms | 1301.7ms |
| 5 | 1.6 | 5,760 | 0.2% | 4218.6ms | 6275.6ms |

---

## Key Findings

- **Worst case latency:** 2354.1ms at 50f × 100e
- **FV scaling impact:** 1 FVs → 377.3ms p99
- **Peak throughput:** 5,760 RPH (0.2% of 3M target)
