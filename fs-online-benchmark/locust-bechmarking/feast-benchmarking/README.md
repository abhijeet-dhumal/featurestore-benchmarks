# Feast Online Store Benchmark Results

Performance benchmark results for Feast feature serving across **4 online stores** and **3 Git branches**.

---

## Executive Summary

![Cross Reference Comparison](results/comparison/charts/01_cross_reference_comparison.png)

### Performance at SLA Target (50 entities × 200 features)

| Store | v0.60.0 | Master | Optimized | Saved | Best For |
|-------|---------|--------|-----------|-------|----------|
| **Redis** | 148ms | 137ms | 103ms | **45ms (30%)** | Production ML inference |
| **SQLite** | 157ms | 134ms | 109ms | **48ms (31%)** | Development, testing |
| **PostgreSQL** | 167ms | 159ms | 124ms | **43ms (26%)** | Existing infrastructure |
| **DynamoDB** | 217ms | 194ms | 164ms | **53ms (25%)** | AWS serverless |

### Key Findings

| Finding | Value | Implication |
|---------|-------|-------------|
| **Total Improvement** | 25-31% | v0.60.0 → Optimized |
| **Master vs v0.60.0** | ~10% | Minor upstream improvements |
| **Optimized vs Master** | ~15-20% | **Our PRs make the difference** |
| **SLA Compliance** | ≤10 entities only | 60ms target requires small batches |

**Bottom Line:** Our 6 PRs deliver **40-53ms savings per request** — the majority of performance gains.

---

## Git References & PRs

| Branch | Reference | Purpose |
|--------|-----------|---------|
| **v0.60.0** | `feast-dev/feast@v0.60.0` | Baseline (stable release) |
| **Master** | `feast-dev/feast@master` | Current main (March 2, 2026) |
| **Optimized** | `abhijeet-dhumal/feast@perf/combined-optimizations` | Our PRs |

### Optimization PRs (6 total)

| PR | Improvement | Impact | Status |
|----|-------------|--------|--------|
| [#6003](https://github.com/feast-dev/feast/pull/6003) | Timestamp O(n×m) → O(n) | -5 to -10ms | Open |
| [#6006](https://github.com/feast-dev/feast/pull/6006) | Entity key deduplication | -3 to -5ms | ✅ Merged |
| [#6014](https://github.com/feast-dev/feast/pull/6014) | Registry N+1 fix | -1 to -2ms | ✅ Merged |
| [#6015](https://github.com/feast-dev/feast/pull/6015) | MessageToDict 4x faster | -5 to -15ms | Open |
| [#6023](https://github.com/feast-dev/feast/pull/6023) | Redis protobuf parsing | -2 to -5ms | ✅ Merged |
| [#6024](https://github.com/feast-dev/feast/pull/6024) | DynamoDB parallel batches | -40 to -120ms | Open |

---

## Store Comparison

### Performance Hierarchy

```
Fastest ──────────────────────────────────────────── Slowest

   Redis  <  SQLite  <  PostgreSQL  <  DynamoDB
   
   @ 1 entity:    ~5ms     ~6ms       ~7ms         ~9ms
   @ 50 entities: ~103ms   ~109ms     ~124ms       ~164ms
   @ 500 entities: ~635ms  ~692ms     ~1004ms      ~1023ms
```

### Store Characteristics

| Store | Strengths | Bottleneck | Best For |
|-------|-----------|------------|----------|
| **Redis** | Lowest latency, best scaling | Protobuf serialization (20-27%) | Production ML inference |
| **SQLite** | No network, highest improvement % | Disk I/O at scale | Dev/test, cost-sensitive |
| **PostgreSQL** | Consistent, predictable | Connection pooling | Existing Postgres teams |
| **DynamoDB** | Auto-scaling, managed | Sequential batch calls | AWS serverless |

### SLA Compliance Matrix

| Entity Count | Redis | SQLite | Postgres | DynamoDB |
|--------------|-------|--------|----------|----------|
| 1 entity | ✅ 5ms | ✅ 6ms | ✅ 7ms | ✅ 9ms |
| 10 entities | ❌ 12ms | ❌ 54ms | ❌ 73ms | ❌ 28ms |
| 50 entities | ❌ 103ms | ❌ 109ms | ❌ 124ms | ❌ 164ms |

**60ms SLA met only at ≤10 entities with Redis.**

---

## Bottleneck Analysis

### Time Breakdown (50 entities × 200 features)

```
├── Feast SDK Overhead:     ~86ms (46%)  ← Largest contributor
├── Protobuf Serialization: ~42ms (22%)  ← PR #6015 targets this
├── Timestamp Handling:     ~27ms (14%)  ← PR #6003 targets this
├── Online Store Read:      ~23ms (12%)  ← Database is NOT the bottleneck
└── Miscellaneous:          ~10ms  (6%)
    ─────────────────────────────────────
    Total:                 ~188ms
```

**Key Insight:** Database read is only 12% of latency. The bottleneck is SDK overhead.

---

## Detailed Charts

### Entity Scaling (P99 Latency by Entity Count)

**What this shows:** How latency grows as you request more entities (1 → 500) with fixed 200 features.

**What to look for:**
- Bar heights increase left-to-right (more entities = higher latency)
- Red dashed line = 60ms SLA target; bars below = PASS
- Compare same entity count across branches to see improvement
- Redis (blue) consistently shortest bars = fastest store

**Key insight:** Only 1-10 entity requests meet SLA. Optimized branch shows noticeably shorter bars.

**v0.60.0 (Baseline):**
![v0.60.0](results/v0.60.0/charts/01_latency_by_entities.png)

**Master:**
![master](results/master/charts/01_latency_by_entities.png)

**Optimized:**
![optimized](results/optimized/charts/01_latency_by_entities.png)

---

### Feature Scaling (P99 Latency by Feature Count)

**What this shows:** How latency grows as you request more features (5 → 200) with fixed 50 entities.

**What to look for:**
- Bar heights increase with feature count (serialization overhead)
- Compare v0.60.0 → Master → Optimized: bars get progressively shorter
- All stores fail SLA at 50+ features (with 50 entities)

**Key insight:** Latency grows linearly with features due to protobuf serialization. Our PRs reduce this overhead by 25-30%.

**v0.60.0 (Baseline):**
![v0.60.0](results/v0.60.0/charts/01b_latency_by_features.png)

**Master:**
![master](results/master/charts/01b_latency_by_features.png)

**Optimized:**
![optimized](results/optimized/charts/01b_latency_by_features.png)

---

### Production SLA Analysis

**What this shows:** Log-scale view of latency vs entity count with clear SLA zone visualization.

**What to look for:**
- Red horizontal band = 60ms SLA zone
- Points below/in band = PASS, above = FAIL
- Annotations show exact gap to SLA ("Xms over" or "Xms under")
- Trend lines show scaling behavior

**Key insight:** Identifies exact entity count where SLA fails (~10-15 entities). Useful for capacity planning.

**v0.60.0 (Baseline):**
![v0.60.0](results/v0.60.0/charts/02_production_sla.png)

**Master:**
![master](results/master/charts/02_production_sla.png)

**Optimized:**
![optimized](results/optimized/charts/02_production_sla.png)

---

### Executive Summary (4-Panel Overview)

**What this shows:** Single-image overview for stakeholder presentations.

**What to look for:**
- **Top-left:** Quick latency comparison bars
- **Top-right:** Scaling curves on log-log scale
- **Bottom-left:** SLA pass/fail matrix (green=pass, red=fail)
- **Bottom-right:** Store ranking at each scale

**Key insight:** At-a-glance verdict — scan green/red cells to see which configs pass SLA.

**v0.60.0 (Baseline):**
![v0.60.0](results/v0.60.0/charts/03_executive_summary.png)

**Master:**
![master](results/master/charts/03_executive_summary.png)

**Optimized:**
![optimized](results/optimized/charts/03_executive_summary.png)

---

### Bottleneck Breakdown (Function-Level)

**What this shows:** Top 12 time-consuming functions in the Feast SDK hot path.

**What to look for:**
- Longer bars = more time in that function
- Percentages show contribution to total latency
- Compare same function across branches to see PR impact
- `_convert_rows_to_protobuf` and `FromDatetime` are top targets

**Key insight:** Database read is small (~12%). SDK overhead dominates. Our PRs target `FromDatetime` (#6003) and `MessageToDict` (#6015).

**v0.60.0 (Baseline):**
![v0.60.0](results/v0.60.0/charts/05_bottleneck_breakdown.png)

**Master:**
![master](results/master/charts/05_bottleneck_breakdown.png)

**Optimized:**
![optimized](results/optimized/charts/05_bottleneck_breakdown.png)

---

## Production Recommendations

### For SLA Compliance (≤60ms P99)

1. Use **Redis** with ≤10 entities per request
2. Keep feature count ≤25 for larger batches
3. Apply all 6 PRs for 25-30% improvement

### Store Selection Guide

| Use Case | Recommended | Rationale |
|----------|-------------|-----------|
| Production ML inference | Redis | Lowest P99 |
| Development/Testing | SQLite | Zero setup |
| AWS native | DynamoDB | Auto-scaling |
| Existing Postgres | PostgreSQL | No new infra |

### If SLA Still Not Met

| Option | Trade-off |
|--------|-----------|
| Tiered SLA (60ms @ 10 entities) | Documentation change |
| Horizontal scaling (2-4x replicas) | Infrastructure cost |
| Client-side batching | Application change |

---

## Reproducing Results

```bash
git clone -b perf-online-feat https://github.com/abhijeet-dhumal/featurestore-benchmarks.git
cd featurestore-benchmarks/fs-online-benchmark/locust-bechmarking/feast-benchmarking

# Run benchmarks
./run_full_benchmark.sh --feast-ref "v0.60.0"
./run_full_benchmark.sh --feast-ref "master"
./run_full_benchmark.sh --feast-ref "optimized"

# Generate charts
python scripts/generate_charts.py --compare-refs --results-base results
```

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for detailed setup instructions.

---

## Links

- [Setup Instructions](INSTRUCTIONS.md)
- [JIRA Epic: RHOAIENG-46061](https://issues.redhat.com/browse/RHOAIENG-46061)
- PRs: [#6003](https://github.com/feast-dev/feast/pull/6003) | [#6006](https://github.com/feast-dev/feast/pull/6006) | [#6014](https://github.com/feast-dev/feast/pull/6014) | [#6015](https://github.com/feast-dev/feast/pull/6015) | [#6023](https://github.com/feast-dev/feast/pull/6023) | [#6024](https://github.com/feast-dev/feast/pull/6024)

---

*Last updated: March 2, 2026*
