# Feast Benchmark Report - DYNAMODB

**Generated:** 2026-02-23 20:51:03  
**Feast Version:** 0.60.0  
**Online Store:** dynamodb  
**SLA Target:** 60ms p99

## Summary

- **Total Tests:** 4
- **SLA Pass Rate:** 0.0%

---

## Latency Matrix (Features × Entities)

| Features | Entities | p50 (ms) | p95 (ms) | p99 (ms) | SLA | Breakdown |
|----------|----------|----------|----------|----------|-----|-----------|
| 50 | 1 | 161.8 | 212.6 | 212.6 | ❌ | read=95% proto=0% |
| 50 | 10 | 342.6 | 376.8 | 376.8 | ❌ | read=97% proto=1% |
| 50 | 100 | 418.1 | 826.2 | 826.2 | ❌ | read=96% proto=2% |

---

## Feature View Scaling

| FVs | Total Features | Entities | p99 (ms) | SLA |
|-----|----------------|----------|----------|-----|
| 1 | 10 | 100 | 334.3 | ❌ |

---

## Transformation Overhead

| Mode | Entities | p50 (ms) | p99 (ms) | SLA |
|------|----------|----------|----------|-----|

---

## Throughput

| Workers | RPS | RPH | Target (3M) | Avg Latency | p99 Latency |
|---------|-----|-----|-------------|-------------|-------------|
| 1 | 6.0 | 21,600 | 0.7% | 167.2ms | 330.9ms |
| 5 | 25.6 | 92,160 | 3.1% | 202.7ms | 725.0ms |

---

## Key Findings

- **Worst case latency:** 826.2ms at 50f × 100e
- **FV scaling impact:** 1 FVs → 334.3ms p99
- **Peak throughput:** 92,160 RPH (3.1% of 3M target)
