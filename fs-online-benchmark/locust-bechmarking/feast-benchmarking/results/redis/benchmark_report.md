# Feast Benchmark Report - REDIS

**Generated:** 2026-02-23 20:50:05  
**Feast Version:** 0.60.0  
**Online Store:** redis  
**SLA Target:** 60ms p99

## Summary

- **Total Tests:** 4
- **SLA Pass Rate:** 0.0%

---

## Latency Matrix (Features × Entities)

| Features | Entities | p50 (ms) | p95 (ms) | p99 (ms) | SLA | Breakdown |
|----------|----------|----------|----------|----------|-----|-----------|
| 50 | 1 | 164.1 | 185.4 | 185.4 | ❌ | read=93% proto=0% |
| 50 | 10 | 172.9 | 179.1 | 179.1 | ❌ | read=93% proto=2% |
| 50 | 100 | 212.5 | 422.8 | 422.8 | ❌ | read=90% proto=6% |

---

## Feature View Scaling

| FVs | Total Features | Entities | p99 (ms) | SLA |
|-----|----------------|----------|----------|-----|
| 1 | 10 | 100 | 192.8 | ❌ |

---

## Transformation Overhead

| Mode | Entities | p50 (ms) | p99 (ms) | SLA |
|------|----------|----------|----------|-----|

---

## Throughput

| Workers | RPS | RPH | Target (3M) | Avg Latency | p99 Latency |
|---------|-----|-----|-------------|-------------|-------------|
| 1 | 6.0 | 21,600 | 0.7% | 169.7ms | 200.7ms |
| 5 | 25.0 | 90,000 | 3.0% | 205.8ms | 797.8ms |

---

## Key Findings

- **Worst case latency:** 422.8ms at 50f × 100e
- **FV scaling impact:** 1 FVs → 192.8ms p99
- **Peak throughput:** 90,000 RPH (3.0% of 3M target)
