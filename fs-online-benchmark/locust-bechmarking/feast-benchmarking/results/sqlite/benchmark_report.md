# Feast Benchmark Report - SQLITE

**Generated:** 2026-02-23 20:48:26  
**Feast Version:** 0.60.0  
**Online Store:** sqlite  
**SLA Target:** 60ms p99

## Summary

- **Total Tests:** 4
- **SLA Pass Rate:** 100.0%

---

## Latency Matrix (Features × Entities)

| Features | Entities | p50 (ms) | p95 (ms) | p99 (ms) | SLA | Breakdown |
|----------|----------|----------|----------|----------|-----|-----------|
| 50 | 1 | 3.9 | 4.1 | 4.1 | ✅ | read=3% proto=3% |
| 50 | 10 | 5.7 | 5.8 | 5.8 | ✅ | read=15% proto=14% |
| 50 | 100 | 23.3 | 26.6 | 26.6 | ✅ | read=36% proto=33% |

---

## Feature View Scaling

| FVs | Total Features | Entities | p99 (ms) | SLA |
|-----|----------------|----------|----------|-----|
| 1 | 10 | 100 | 3.5 | ✅ |

---

## Transformation Overhead

| Mode | Entities | p50 (ms) | p99 (ms) | SLA |
|------|----------|----------|----------|-----|

---

## Throughput

| Workers | RPS | RPH | Target (3M) | Avg Latency | p99 Latency |
|---------|-----|-----|-------------|-------------|-------------|
| 1 | 365.0 | 1,314,000 | 43.8% | 2.7ms | 3.1ms |
| 5 | 236.0 | 849,600 | 28.3% | 21.2ms | 54.9ms |

---

## Key Findings

- **Worst case latency:** 26.6ms at 50f × 100e
- **Primary bottleneck:** protobuf conversion (33%)
- **FV scaling impact:** 1 FVs → 3.5ms p99
- **Peak throughput:** 1,314,000 RPH (43.8% of 3M target)
