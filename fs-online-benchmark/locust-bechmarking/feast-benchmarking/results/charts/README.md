# Feast Online Store Benchmark Results

Performance benchmark results for Feast feature serving across 4 online stores.

---

## Benchmark Framework

### Origin

This benchmark framework is a fork of [featurestoreorg/featurestore-benchmarks](https://github.com/featurestoreorg/featurestore-benchmarks), an open-source project for benchmarking feature stores. This fork extends it with:

- **Unified Python benchmark** (`unified_benchmark.py`) for consistent cross-store testing
- **Kubernetes deployment** with kustomize overlays for in-cluster benchmarking
- **Automated orchestration** (`run_full_benchmark.sh`) for end-to-end execution
- **Visualization suite** (`generate_charts.py`) generating 11 analysis charts
- **Bottleneck profiler** (`analyze_bottlenecks.py`) for function-level analysis

**Upstream repo:** [featurestoreorg/featurestore-benchmarks](https://github.com/featurestoreorg/featurestore-benchmarks)  
**Our fork:** [abhijeet-dhumal/featurestore-benchmarks](https://github.com/abhijeet-dhumal/featurestore-benchmarks/tree/perf-online-feat) (branch: `perf-online-feat`)

### Feast Version

| Component | Version | Notes |
|-----------|---------|-------|
| **Feast SDK** | 0.60.0 | Latest stable at time of testing |
| **Python** | 3.12 | Required for performance |
| **Protobuf** | 4.x | Used for feature serialization |

### Dataset Configuration

**Upstream Framework (featurestoreorg):**

The original [featurestore-benchmarks](https://github.com/featurestoreorg/featurestore-benchmarks) uses the **NYC Taxi dataset**:
- **Dataset:** NYC Taxi Trip data (500 records subset)
- **Source:** [rides500.csv](https://repo.hops.works/dev/davit/nyc_taxi/rides500.csv)
- **Features:** Mixed data types (timestamps, floats, strings, integers)
- **Use case:** Realistic taxi ride data with pickup/dropoff locations, fares, etc.

**Our Fork (feast-benchmarking):**

Our benchmark uses a **synthetic dataset** generated at runtime for consistent, reproducible testing:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Entity** | `user_id` (STRING) | Common use case (user/driver/item ID) |
| **Feature Count** | 200 (configurable) | Realistic for ML models |
| **Feature Type** | All `Float64` | Consistent for fair comparison |
| **Feature View** | Single (`fv_0`) | Isolates retrieval performance |
| **Feature Names** | `fv0_f0`, `fv0_f1`, ... `fv0_f199` | Generated programmatically |
| **Data Volume** | 500+ entities | Pre-materialized before benchmark |
| **Data Source** | Parquet file (generated) | FileSource with timestamp field |
| **TTL** | 1 day | Standard expiration |

**Data Generation (from `unified_benchmark.py`):**
```python
# Entity definition
user = Entity(
    name="user_id",
    join_keys=["user_id"],
    value_type=ValueType.STRING
)

# Feature View with N Float64 features
fv = FeatureView(
    name="fv_0",
    entities=[user],
    schema=[Field(name=f"fv0_f{i}", dtype=Float64) for i in range(num_features)],
    source=FileSource(path=parquet_path, timestamp_field="event_timestamp"),
    ttl=timedelta(days=1)
)

# Entity rows for requests
entity_rows = [{"user_id": f"user_{i}"} for i in range(num_entities)]
```

### Why Synthetic Data Instead of NYC Taxi?

| Aspect | NYC Taxi (Upstream) | Synthetic (Our Fork) |
|--------|---------------------|----------------------|
| **Features** | ~20 mixed types | 200 Float64 |
| **Records** | 500 fixed | Configurable |
| **Reproducibility** | Requires download | Generated on-the-fly |
| **Feature count** | Limited | Matches production (200) |
| **Type variance** | Mixed (noisy) | Consistent (fair comparison) |

**Why we chose synthetic:**

| Design Choice | Reason |
|---------------|--------|
| **200 features** | Matches production requirement (not 20) |
| **All Float64** | Eliminates type serialization variance for fair store comparison |
| **Configurable entities** | Test 1 to 500+ entities per request |
| **No external deps** | No network download, runs anywhere |
| **Reproducible** | Same data every run for consistent benchmarks |

---

## Agenda & Objective

**Goal:** Evaluate if Feast can meet production SLA requirements:
- **Target SLA:** 60ms p99 latency
- **Target Throughput:** 3M transactions/hour
- **Workload:** 200 features × up to 500 entities per request

**Why This Matters:**
- Production ML inference requires low-latency feature retrieval
- High entity counts are common in batch-style online requests (e.g., recommendations, fraud detection)
- Missing SLA impacts user experience and system reliability

---

## Test Configuration

| Parameter | Value | Why |
|-----------|-------|-----|
| **Features** | 200 | Realistic production feature count |
| **Entity Counts** | 1, 10, 50, 100, 200, 500 | Tests scaling behavior |
| **Iterations** | 100 | Statistical significance for p99 |
| **Warmup** | 10 | Eliminates cold-start noise |
| **Online Stores** | Redis, Postgres, DynamoDB | Production-grade backends |

---

## Understanding the Metrics

### Latency Metrics

| Metric | Definition | What It Means |
|--------|------------|---------------|
| **p50 (median)** | 50% of requests are faster than this | Typical user experience |
| **p95** | 95% of requests are faster than this | Good indicator of consistent performance |
| **p99** | 99% of requests are faster than this | **SLA metric** - worst case for most users |
| **Mean** | Average latency | Can be skewed by outliers |
| **Std Dev** | Variation in latency | Lower = more predictable |

**Why p99?** Production SLAs use p99 because it represents the worst experience for 99% of users. If p99 is 60ms, only 1 in 100 requests will be slower.

### Scaling Behavior

| Pattern | What It Means | Implication |
|---------|---------------|-------------|
| **O(1)** | Constant time regardless of entities | Ideal - no scaling issues |
| **O(n)** | Linear scaling with entities | Per-entity overhead exists |
| **O(n²)** | Quadratic scaling | Serious algorithmic issue |

**Current finding:** Feast shows O(n) scaling - latency grows linearly with entity count.

---

## Chart Descriptions

### 01_latency_by_entities.png
**P99 Latency by Entity Count**

![01_latency_by_entities](01_latency_by_entities.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis** | Entity count (1, 10, 50, 100, 200, 500) - number of entities per request |
| **Y-axis** | P99 latency in milliseconds - 99th percentile response time |
| **Bars** | Grouped by entity count, colored by store (Redis=blue, SQLite=orange, Postgres=green, DynamoDB=red) |
| **Red dashed line** | 60ms SLA target - bars below this line = PASS |

**How to Read:**
- Compare bar heights within each group to see which store is fastest at that entity count
- Compare bar heights across groups to see how latency grows with entities
- Any bar above the red line means SLA failure

**Why This Matters:**
- Shows at-a-glance which configurations meet SLA
- Reveals that only 1-entity requests are viable for production
- Demonstrates Redis consistently outperforms other stores

**Key Takeaway:** All stores pass SLA only at 1 entity. Redis is consistently fastest.

---

### 02_scaling_curves.png
**Scaling Behavior (Log-Log)**

![02_scaling_curves](02_scaling_curves.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis (log scale)** | Entity count (1 to 500) - logarithmic scale |
| **Y-axis (log scale)** | P99 latency in ms - logarithmic scale |
| **Lines** | One per store, showing latency growth pattern |
| **Slope** | Indicates scaling complexity: slope=1 means O(n), slope=2 means O(n²) |

**How to Read:**
- **Straight line on log-log** = polynomial scaling (O(n^slope))
- **Slope ≈ 1** = linear scaling O(n) - latency doubles when entities double
- **Slope > 1** = worse than linear - indicates algorithmic inefficiency
- **Parallel lines** = all stores have same scaling behavior, just different baselines

**Why This Matters:**
- Log-log plots reveal algorithmic complexity
- If slope was 0, latency would be constant (ideal)
- Slope ≈ 1 confirms per-entity overhead (~2ms per entity)
- Changing store doesn't change the slope - the SDK is the bottleneck

**Key Takeaway:** O(n) linear scaling - latency grows proportionally with entity count. Store choice affects baseline but not scaling behavior.

---

### 03_store_ranking.png
**Store Performance Ranking**

![03_store_ranking](03_store_ranking.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis** | Online store names |
| **Y-axis** | P99 latency in milliseconds |
| **Bar groups** | Separate bars for different entity counts (1, 100, 500) |
| **Bar height** | Lower = faster = better |

**How to Read:**
- Compare bars within same entity count to rank stores
- Leftmost store in each comparison is fastest
- Gap between bars shows relative performance difference

**Why This Matters:**
- Guides production store selection
- Shows Redis advantage increases at scale (12% faster at 1 entity, 45% faster at 500)
- DynamoDB's managed convenience comes with performance cost

**Key Takeaway:** 
- **Ranking:** Redis > SQLite > Postgres > DynamoDB
- Redis is 12-45% faster than alternatives at scale

---

### 04_time_breakdown.png
**Time Breakdown (Stacked Bar)**

![04_time_breakdown](04_time_breakdown.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis** | Online store names |
| **Y-axis** | Total latency in milliseconds |
| **Stacked segments** | Time spent in each component |
| **Colors** | Blue=Online Read, Orange=Serialization, Green=Entity Encoding, Purple=Other |

**Component Definitions:**
| Component | What It Measures | Code Location |
|-----------|------------------|---------------|
| **Online Store Read** | Time to fetch data from Redis/Postgres/etc | `online_store.online_read()` |
| **Serialization** | Protobuf → Python dict conversion | `MessageToDict()`, response encoding |
| **Entity Key Encoding** | Converting entity IDs to storage keys | `serialize_entity_key()` |
| **Other** | Registry lookups, network overhead, etc | Various |

**How to Read:**
- Segment height = time spent in that component
- Total bar height = total latency
- Compare segment proportions across stores
- Largest segment = primary bottleneck to fix

**Why This Matters:**
- Reveals WHERE to focus optimization efforts
- Shows serialization is 80% of time, not database
- Changing store saves ~20%, fixing serialization saves ~80%

**Key Takeaway:** Serialization/protobuf overhead dominates (~80%), not database reads (~20%).

---

### 05_sla_gap_analysis.png
**SLA Gap Analysis**

![05_sla_gap_analysis](05_sla_gap_analysis.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis** | Entity count |
| **Y-axis** | Multiplier over SLA (actual_latency / 60ms) |
| **Lines** | One per store |
| **Reference line at y=1** | Values above this line = SLA failure |
| **Value 1.0** | Exactly at 60ms SLA |
| **Value 2.0** | 2x over SLA (120ms actual) |
| **Value 16.5** | 16.5x over SLA (990ms actual) |

**How to Read:**
- y=1 means exactly meeting SLA
- y<1 means faster than SLA (passing)
- y>1 means slower than SLA (failing)
- Higher values = worse performance gap

**Why This Matters:**
- Quantifies how far we are from the target
- "16x over SLA" is more impactful than "930ms over"
- Shows the gap grows with entity count

**Key Takeaway:** At 500 entities, latency is 16-24x over SLA depending on store.

---

### 06_executive_summary.png
**Executive Summary (4-Panel)**

![06_executive_summary](06_executive_summary.png)

**Graph Parameters:**
| Panel | Content | Purpose |
|-------|---------|---------|
| **Top-left** | P99 latency bars by entity count | Quick latency comparison |
| **Top-right** | Scaling curves (log-log) | Growth pattern |
| **Bottom-left** | SLA pass/fail matrix | Green=pass, Red=fail |
| **Bottom-right** | Store ranking summary | Winner at each scale |

**How to Read:**
- Scan all 4 panels for complete picture
- Green cells = good, Red cells = bad
- Use for stakeholder presentations

**Why This Matters:**
- Single image for executive communication
- No need to explain 10 separate charts
- Clear pass/fail verdict at a glance

**Key Takeaway:** Quick overview for stakeholders - only 1-entity requests meet SLA.

---

### 07_production_sla.png
**Production SLA Analysis**

![07_production_sla](07_production_sla.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis** | Entity count (log scale) |
| **Y-axis** | P99 latency in ms (log scale) |
| **Red horizontal band** | 60ms SLA zone - target area |
| **Annotations** | Callouts showing exact values and gaps |
| **Color coding** | Green points=pass, Red points=fail |

**How to Read:**
- Points in the red band = meeting SLA
- Points above the band = failing SLA
- Annotations show "Xms over SLA" or "Xms under SLA"
- Trend line shows expected latency at unmeasured entity counts

**Why This Matters:**
- Production-focused view with clear SLA zone
- Shows exact gap to target at each point
- Useful for capacity planning ("at what entity count do we hit SLA?")

**Key Takeaway:** Clear visualization showing ~5-10 entities is the SLA boundary.

---

### 08_bottleneck_breakdown.png
**Function-Level Bottleneck Analysis**

![08_bottleneck_breakdown](08_bottleneck_breakdown.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **One panel per store** | Redis, Postgres, DynamoDB (only benchmarked stores) |
| **Horizontal bars** | Top 12 time-consuming functions |
| **Bar labels** | Time (ms), percentage of total, call count |
| **Title per panel** | Store name with total latency (mean and p99) |
| **Config box** | Shows "50 entities × 200 features" |
| **SLA status** | [PASS] or [FAIL] based on p99 vs 60ms |

**How to Read:**
- Longer bars = more time spent in that function
- Percentages show relative contribution to total latency
- Call counts in brackets (e.g., [500 calls]) indicate hot paths
- Compare same functions across stores to identify store-specific bottlenecks

**Why This Matters:**
- Identifies exact functions to optimize
- Shows which functions dominate across ALL stores (SDK bottlenecks)
- Reveals store-specific vs common issues

**Key Takeaway:** `_convert_rows_to_protobuf`, `construct_response_feature_vector`, and `FromDatetime` are top bottlenecks across all stores.

---

### 09_category_comparison.png
**Time Breakdown by Category**

![09_category_comparison](09_category_comparison.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis** | Categories: DB/Store Read, Protobuf/Serialization, Timestamp Handling, Type Checking, Other |
| **Y-axis** | Time in milliseconds |
| **Grouped bars** | One bar per store within each category |
| **Bar labels** | Time (ms) and percentage |
| **Legend** | Store name with total latency and p99 SLA status |
| **Red dashed line** | 60ms SLA reference |
| **Config box** | Shows entity × feature configuration |

**How to Read:**
- Compare bar heights within each category to see which store is fastest
- Look at "Other" category - if it's largest, there are uncategorized bottlenecks
- Bars above 60ms line indicate that single category exceeds SLA

**Why This Matters:**
- Groups functions into actionable categories
- Shows which category contributes most to latency
- Helps prioritize optimization areas

**Key Takeaway:** "Other" category is significant (55-80%), indicating type checking, validation, and miscellaneous overhead needs investigation.

---

### 10_optimization_waterfall.png
**Time Breakdown Waterfall**

![10_optimization_waterfall](10_optimization_waterfall.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **One row per store** | Redis, Postgres, DynamoDB |
| **Stacked segments** | Time spent in each category, laid out horizontally |
| **Segment colors** | Consistent category colors across stores |
| **Labels inside segments** | Category name, time (ms), percentage |
| **Red dashed line** | 60ms SLA reference |
| **Title per row** | Store with total latency and SLA status |

**How to Read:**
- Width of each segment = time spent in that category
- Total bar width = total latency
- Segments to the left of the 60ms line are within SLA budget
- Segments extending past 60ms show where optimization is needed

**Why This Matters:**
- Visual "budget" view of where time goes
- Shows cumulative effect of each category
- Clear indication of how much needs to be trimmed to meet SLA

**Key Takeaway:** For all stores, "Other" + "Protobuf" segments push the total past 60ms SLA.

---

### 11_function_heatmap.png
**Function Time Heatmap**

![11_function_heatmap](11_function_heatmap.png)

**Graph Parameters:**
| Element | Description |
|---------|-------------|
| **X-axis** | Top function names (truncated to 30 chars) |
| **Y-axis** | Store names with total latency and SLA status |
| **Cell color** | Heat intensity (darker = more time) |
| **Cell labels** | Time in milliseconds |
| **Color scale** | Yellow (fast) → Red (slow) |
| **Config box** | Shows entity × feature configuration |

**How to Read:**
- Darker cells = more time spent in that function for that store
- Consistent dark column = function is slow across ALL stores (SDK issue)
- Dark row = that store is generally slower
- Compare cells horizontally to find store-specific bottlenecks

**Why This Matters:**
- Cross-store comparison at function level
- Identifies functions that are slow only on certain stores (store-specific optimization)
- Highlights functions slow everywhere (SDK optimization targets)

**Key Takeaway:** `FromDatetime`, `_convert_rows_to_protobuf`, and `construct_response_feature_vector` show up as hot spots across all stores.

---

## Summary Table

### Benchmark Charts (01-07)

| Chart | Purpose | Key Insight |
|-------|---------|-------------|
| 01 | Latency by entities | Only 1 entity meets SLA |
| 02 | Scaling curves | O(n) scaling behavior |
| 03 | Store ranking | Redis > Postgres > DynamoDB |
| 04 | Time breakdown | Stacked view of time by category (from profiling) |
| 05 | SLA gap | 2.6-3.8x over SLA at 50 entities |
| 06 | Executive summary | Quick 4-panel overview (50 entities target) |
| 07 | Production SLA | Detailed gap analysis (50 & 200 entities) |

### Bottleneck Analysis Charts (08-11)

| Chart | Purpose | Key Insight |
|-------|---------|-------------|
| 08 | Bottleneck breakdown | Top functions by time per store |
| 09 | Category comparison | Grouped bars comparing categories across stores |
| 10 | Optimization waterfall | Cumulative time breakdown for each store |
| 11 | Function heatmap | Cross-store function time comparison |

---

## Key Findings

### What the Data Tells Us

| Finding | Evidence | Impact |
|---------|----------|--------|
| **SLA only met for 1 entity** | Chart 01, 06, 07 | Cannot support batch requests |
| **Redis is fastest** | Chart 03, 09 | ~40% faster than Postgres/DynamoDB |
| **"Other" category dominates** | Chart 08, 10 | 55-80% of time is uncategorized overhead |
| **Protobuf/serialization significant** | Chart 09, 10 | 15-17% of time in serialization |
| **Linear scaling O(n)** | Chart 02 | Per-entity overhead ~2ms |
| **2.6-3.8x over SLA at 50 entities** | Chart 06, 07 | Gap to close for production target |

### Root Cause Analysis

The benchmark data reveals that **database choice is NOT the primary bottleneck**.

**Detailed Function-Level Profiling (200 entities, 200 features, SQLite):**

| Function | Time | % | PR |
|----------|------|---|---|
| `infra.online_read` | 22.85ms | 12.1% | Store-specific |
| `utils.construct_response_feature_vector` | 22.07ms | 11.7% | - |
| `utils._convert_rows_to_protobuf` | 19.76ms | 10.5% | PR #6015 |
| **`FromDatetime`** | **18.90ms** | **10.0%** | **PR #6003** |
| `infra.convert_timestamp` | 7.58ms | 4.0% | PR #6003 |
| `infra.get_online_features` | 7.00ms | 3.7% | - |
| `_CheckTimestampValid` | 2.93ms | 1.6% | PR #6003 |
| `infra.serialize_entity_key` | 1.09ms | 0.6% | PR #6006 |
| Other (type checking, validation) | 86ms | 45.6% | - |
| **TOTAL** | **188ms** | **100%** | |

**Grouped by Category:**

```
Time Breakdown (200 entities, 200 features):
├── Other (type checks, validation):  66.5ms (35%)  ← Significant overhead
├── Online Store Read:                22.9ms (12%)  ← Database is fast
├── Protobuf/Serialization:           20.8ms (11%)  ← PR #6015
├── Timestamp Functions:              29.4ms (16%)  ← PR #6003 (combined)
├── Entity Key Handling:               1.1ms  (1%)  ← PR #6006
└── Registry/Metadata:                 0.8ms  (<1%) ← PR #6014
    ────────────────────────────────────────────────
    Total:                           188.0ms
```

**Key Insight:** Timestamp-related functions (`FromDatetime`, `convert_timestamp`, `_CheckTimestampValid`) account for **29.4ms (16%)** - this is what PR #6003 targets.

**To reproduce this profiling locally:**
```bash
python profile_breakdown.py --entities 200 --features 200 --iterations 10
```

---

## What This Means for Our Agenda

### Current State vs Requirements (50 entities × 200 features)

| Store | p99 Latency | SLA (60ms) | Gap |
|-------|-------------|------------|-----|
| **Redis** | 156ms | ❌ FAIL | 2.6x over |
| **Postgres** | 216ms | ❌ FAIL | 3.6x over |
| **DynamoDB** | 229ms | ❌ FAIL | 3.8x over |

| Requirement | Target | Best (Redis) | Status |
|-------------|--------|--------------|--------|
| p99 @ 1 entity | 60ms | ~15ms | ✅ Met |
| p99 @ 50 entities | 60ms | 156ms | ❌ 2.6x over |
| p99 @ 200 entities | 60ms | ~400ms | ❌ ~6.7x over |
| Throughput | 3M txn/hr | Not tested | ⚠️ Pending |

### Implications

1. **Single-entity requests:** Production-ready with Redis
2. **Batch requests (10+ entities):** NOT production-ready
3. **Store selection:** Redis is optimal, but won't solve the SLA gap alone
4. **Architecture changes:** May be needed if PRs don't close the gap

---

## Next Steps

### Immediate Actions (Blocked on PR Merges)

| Priority | Action | Owner | Status | Expected Impact |
|----------|--------|-------|--------|-----------------|
| 🔴 Critical | Merge [PR #6003](https://github.com/feast-dev/feast/pull/6003) | Upstream | ⏳ Review | -5 to -10ms |
| 🔴 Critical | Merge [PR #6006](https://github.com/feast-dev/feast/pull/6006) | Upstream | ⏳ Review | -3 to -5ms |
| 🔴 Critical | Merge [PR #6014](https://github.com/feast-dev/feast/pull/6014) | Upstream | ⏳ Review | -1 to -2ms |
| 🔴 Critical | Merge [PR #6015](https://github.com/feast-dev/feast/pull/6015) | Upstream | ⏳ Review | -9ms (4x faster) |

**Combined expected improvement: ~15-25ms per request**

### After PR Merges

| Priority | Action | Purpose |
|----------|--------|---------|
| 🟠 High | Re-run benchmarks | Validate improvements |
| 🟠 High | Throughput testing | Validate 3M txn/hr |
| 🟡 Medium | Concurrent load testing | Multi-client behavior |
| 🟡 Medium | Horizontal scaling | Test 4, 8, 16 replicas |

### If PRs Don't Close the Gap

| Option | Description | Trade-off |
|--------|-------------|-----------|
| **Batch API** | New endpoint for bulk requests | Requires API change |
| **Streaming** | gRPC streaming instead of request/response | Client SDK changes |
| **Caching layer** | Cache hot features in-memory | Staleness risk |
| **Custom serialization** | Replace Protobuf with faster format | Compatibility |

---

## Reproducing These Results

```bash
# Clone and setup
git clone -b perf-online-feat https://github.com/abhijeet-dhumal/featurestore-benchmarks.git
cd featurestore-benchmarks/fs-online-benchmark/locust-bechmarking/feast-benchmarking

# Setup environment
python3 -m venv .venv
./.venv/bin/pip install feast matplotlib numpy pandas

# Deploy infrastructure
oc apply -k k8s/base
oc apply -k k8s/stores

# Run benchmarks
./run_full_benchmark.sh

# Results will be in results/charts/
```

---

## Links

**Benchmark Framework:**
- [Full Benchmark README](https://github.com/abhijeet-dhumal/featurestore-benchmarks/blob/perf-online-feat/fs-online-benchmark/locust-bechmarking/feast-benchmarking/README.md)

**PRs for Review:**
- [PR #6003](https://github.com/feast-dev/feast/pull/6003) - Timestamp conversion fix
- [PR #6006](https://github.com/feast-dev/feast/pull/6006) - Entity key serialization fix
- [PR #6014](https://github.com/feast-dev/feast/pull/6014) - Registry lookup fix
- [PR #6015](https://github.com/feast-dev/feast/pull/6015) - MessageToDict optimization

**Issues:**
- [#6004](https://github.com/feast-dev/feast/issues/6004) - Timestamp conversion overhead
- [#6005](https://github.com/feast-dev/feast/issues/6005) - Redundant entity key serialization
- [#6012](https://github.com/feast-dev/feast/issues/6012) - Redundant registry.get_entity() calls
- [#6013](https://github.com/feast-dev/feast/issues/6013) - Slow MessageToDict serialization

**JIRA:**
- [RHOAIENG-50013](https://issues.redhat.com/browse/RHOAIENG-50013) - Performance tracking issue
