# Feast Benchmark Workflow - Visual Guide

## What is Feast?

Feast is a **Feature Store** - a system that stores and serves features (data) for Machine Learning models.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WHAT IS FEAST?                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Raw Data                    Feast                    ML Model     │
│   ─────────                   ─────                    ────────     │
│                                                                     │
│   ┌──────────┐            ┌──────────┐            ┌──────────┐     │
│   │ Database │ ──────────▶│  FEAST   │ ──────────▶│  Model   │     │
│   │ CSV      │  Features  │ Feature  │  Features  │ Predicts │     │
│   │ Parquet  │            │  Store   │            │ Outcomes │     │
│   └──────────┘            └──────────┘            └──────────┘     │
│                                                                     │
│   Example: User purchase history → Feast → "Will user buy X?"      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Why Benchmark Feast?

We need to measure **how fast** Feast can serve features to ML models.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     WHY BENCHMARK?                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Goal: Serve features in under 60ms (SLA target)                   │
│                                                                     │
│   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐    │
│   │   Request   │        │    FEAST    │        │  Response   │    │
│   │ "Get user   │───────▶│  Retrieves  │───────▶│  Returns    │    │
│   │  features"  │        │  from store │        │  features   │    │
│   └─────────────┘        └─────────────┘        └─────────────┘    │
│         │                                              │            │
│         │◀────────────── TIME ELAPSED ────────────────▶│            │
│                                                                     │
│   If TIME < 60ms → ✅ PASS                                          │
│   If TIME > 60ms → ❌ FAIL                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Overall Benchmark Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BENCHMARK WORKFLOW OVERVIEW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   STEP 1              STEP 2              STEP 3              STEP 4        │
│   ───────             ───────             ───────             ───────       │
│                                                                             │
│   ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐     │
│   │  SETUP  │───────▶│  RUN    │───────▶│ COLLECT │───────▶│ REPORT  │     │
│   │         │        │  TESTS  │        │ METRICS │        │         │     │
│   └─────────┘        └─────────┘        └─────────┘        └─────────┘     │
│       │                  │                  │                   │           │
│       ▼                  ▼                  ▼                   ▼           │
│   • Create data      • Send many        • Record times      • Charts       │
│   • Configure        • requests         • Calculate p50     • Tables       │
│   • online store     • to Feast         • p95, p99         • Markdown     │
│   • Materialize                         • throughput        • JSON/CSV     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Setup (What Gets Created)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            STEP 1: SETUP                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. CREATE TEST DATA                                                       │
│   ────────────────────                                                      │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │  user_id  │  feature_0  │  feature_1  │ ... │  feature_199  │          │
│   ├───────────┼─────────────┼─────────────┼─────┼───────────────┤          │
│   │  user_0   │    0.1      │    0.2      │ ... │    19.9       │          │
│   │  user_1   │    0.2      │    0.3      │ ... │    20.0       │          │
│   │  user_2   │    0.3      │    0.4      │ ... │    20.1       │          │
│   │    ...    │    ...      │    ...      │ ... │    ...        │          │
│   │  user_499 │   50.0      │   50.1      │ ... │    69.9       │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
│   500 users × 200 features = 100,000 data points                           │
│                                                                             │
│                                                                             │
│   2. CONFIGURE ONLINE STORE                                                 │
│   ─────────────────────────                                                 │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────┐         │
│   │  feature_store.yaml                                          │         │
│   ├──────────────────────────────────────────────────────────────┤         │
│   │  project: benchmark                                          │         │
│   │  online_store:                                               │         │
│   │    type: sqlite    ◀── Can be: sqlite, redis, dynamodb, pg   │         │
│   │    path: online.db                                           │         │
│   └──────────────────────────────────────────────────────────────┘         │
│                                                                             │
│                                                                             │
│   3. MATERIALIZE (Load data into online store)                              │
│   ────────────────────────────────────────────                              │
│                                                                             │
│       Parquet File                    Online Store                          │
│       ────────────                    ────────────                          │
│                                                                             │
│       ┌──────────┐   "materialize"   ┌──────────────┐                      │
│       │ Raw Data │ ─────────────────▶│ SQLite/Redis │                      │
│       │ (slow)   │                   │ DynamoDB     │                      │
│       └──────────┘                   │ (fast!)      │                      │
│                                      └──────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 2: Run Tests (What We Measure)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STEP 2: RUN TESTS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   TEST MATRIX - We test different combinations:                             │
│   ─────────────────────────────────────────────                             │
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────┐        │
│   │                                                               │        │
│   │   FEATURES      ×      ENTITIES      =      TESTS             │        │
│   │   ────────             ────────             ─────             │        │
│   │                                                               │        │
│   │   50 features    ×    1 user       =    "small request"       │        │
│   │   50 features    ×    100 users    =    "medium request"      │        │
│   │   200 features   ×    500 users    =    "large request"       │        │
│   │                                                               │        │
│   └───────────────────────────────────────────────────────────────┘        │
│                                                                             │
│                                                                             │
│   SINGLE TEST EXECUTION:                                                    │
│   ──────────────────────                                                    │
│                                                                             │
│                    Request: "Get 50 features for 10 users"                  │
│                                                                             │
│   ┌──────────┐      START TIMER       ┌──────────┐      STOP TIMER         │
│   │          │ ─────────────────────▶ │          │ ──────────────────▶     │
│   │  Python  │                        │  Feast   │                         │
│   │  Script  │ ◀───────────────────── │  Store   │                         │
│   │          │      RETURN DATA       │          │      RECORD: 15.3ms     │
│   └──────────┘                        └──────────┘                         │
│                                                                             │
│                                                                             │
│   REPEAT 20 TIMES:                                                          │
│   ────────────────                                                          │
│                                                                             │
│   Run 1:  15.3ms                                                            │
│   Run 2:  14.8ms                                                            │
│   Run 3:  16.1ms                                                            │
│   Run 4:  15.0ms                                                            │
│   ...                                                                       │
│   Run 20: 15.5ms                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 3: Collect Metrics (What Numbers Mean)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STEP 3: COLLECT METRICS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   FROM 20 MEASUREMENTS, CALCULATE:                                          │
│   ────────────────────────────────                                          │
│                                                                             │
│   Raw measurements (sorted):                                                │
│   [12.1, 13.2, 14.0, 14.5, 14.8, 15.0, 15.1, 15.2, 15.3, 15.3,             │
│    15.4, 15.5, 15.6, 15.7, 15.8, 16.0, 16.2, 16.5, 17.1, 18.9]             │
│                                                                             │
│                                                                             │
│   p50 (median) = 15.3ms                                                     │
│   ─────────────────────                                                     │
│   "50% of requests are faster than this"                                    │
│                                    │                                        │
│      ├─────────────────────────────┼─────────────────────────────┤         │
│      │  faster 50%                 │  slower 50%                 │         │
│                                                                             │
│                                                                             │
│   p95 = 16.5ms                                                              │
│   ────────────                                                              │
│   "95% of requests are faster than this"                                    │
│                                                      │                      │
│      ├───────────────────────────────────────────────┼───────┤             │
│      │  faster 95%                                   │ slow  │             │
│                                                       5%                    │
│                                                                             │
│   p99 = 18.9ms  ◀── THIS IS THE KEY METRIC FOR SLA                         │
│   ────────────                                                              │
│   "99% of requests are faster than this"                                    │
│                                                            │                │
│      ├─────────────────────────────────────────────────────┼─┤             │
│      │  faster 99%                                         │1│             │
│                                                            %               │
│                                                                             │
│   WHY p99?                                                                  │
│   ────────                                                                  │
│   p99 catches the "worst case" (excluding outliers)                        │
│   If p99 < 60ms → 99% of your users get fast responses                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 4: Generate Reports

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STEP 4: GENERATE REPORTS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   OUTPUT FILES:                                                             │
│   ─────────────                                                             │
│                                                                             │
│   results/                                                                  │
│   ├── benchmark_results.json    ← Raw data (for programs)                   │
│   ├── benchmark_summary.csv     ← Table (for spreadsheets)                  │
│   ├── benchmark_report.md       ← Human-readable report                     │
│   ├── *_heatmap.png             ← Visual: latency by config                 │
│   ├── *_breakdown.png           ← Visual: where time is spent               │
│   └── *_throughput.png          ← Visual: requests per second               │
│                                                                             │
│                                                                             │
│   SAMPLE REPORT TABLE:                                                      │
│   ────────────────────                                                      │
│                                                                             │
│   ┌──────────┬──────────┬──────────┬──────────┬──────────┬─────┐           │
│   │ Features │ Entities │ p50 (ms) │ p95 (ms) │ p99 (ms) │ SLA │           │
│   ├──────────┼──────────┼──────────┼──────────┼──────────┼─────┤           │
│   │    50    │     1    │   2.1    │   3.5    │   4.2    │ ✅  │           │
│   │    50    │    10    │   5.3    │   8.1    │  10.4    │ ✅  │           │
│   │    50    │   100    │  15.3    │  22.1    │  28.4    │ ✅  │           │
│   │    50    │   500    │  89.2    │ 124.5    │ 156.3    │ ❌  │           │
│   │   200    │     1    │   8.2    │  12.3    │  15.1    │ ✅  │           │
│   │   200    │   500    │ 312.4    │ 456.2    │ 521.8    │ ❌  │           │
│   └──────────┴──────────┴──────────┴──────────┴──────────┴─────┘           │
│                                                                             │
│   SLA Target: p99 < 60ms                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Function Breakdown (Where Time Goes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FUNCTION BREAKDOWN - WHERE TIME GOES                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   A single request (15ms total) breaks down like this:                      │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │                                                                 │      │
│   │  ┌────────────────────┐  ← online_read (40%)                   │      │
│   │  │                    │    Time spent reading from             │      │
│   │  │    ONLINE READ     │    SQLite/Redis/DynamoDB               │      │
│   │  │      6.0ms         │                                        │      │
│   │  └────────────────────┘                                        │      │
│   │                                                                 │      │
│   │  ┌───────────────┐  ← protobuf_convert (35%)                   │      │
│   │  │               │    Converting data to/from                  │      │
│   │  │   PROTOBUF    │    wire format (serialization)             │      │
│   │  │    5.3ms      │                                            │      │
│   │  └───────────────┘                                             │      │
│   │                                                                 │      │
│   │  ┌──────────┐  ← entity_serialization (15%)                    │      │
│   │  │ ENTITY   │    Encoding user IDs                             │      │
│   │  │  2.2ms   │                                                  │      │
│   │  └──────────┘                                                  │      │
│   │                                                                 │      │
│   │  ┌─────┐  ← other (10%)                                        │      │
│   │  │OTHER│    Python overhead, etc.                              │      │
│   │  │1.5ms│                                                       │      │
│   │  └─────┘                                                       │      │
│   │                                                                 │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│   This tells us: "protobuf_convert is taking 35% - that's the bottleneck!" │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Different Online Stores Explained

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ONLINE STORES COMPARED                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SQLITE (Local file)                                                       │
│   ────────────────────                                                      │
│   ┌─────────────┐     ┌─────────────┐                                      │
│   │   Python    │────▶│  .db file   │  Fast for small tests                │
│   │   Script    │◀────│  (on disk)  │  No network latency                  │
│   └─────────────┘     └─────────────┘  Not for production                  │
│                                                                             │
│                                                                             │
│   REDIS (In-memory)                                                         │
│   ─────────────────                                                         │
│   ┌─────────────┐     ┌─────────────┐                                      │
│   │   Python    │────▶│   Redis     │  Super fast (in memory)              │
│   │   Script    │◀────│   Server    │  Good for production                 │
│   └─────────────┘     └─────────────┘  Requires running server             │
│         │                   │                                              │
│         └───── Network ─────┘                                              │
│                                                                             │
│                                                                             │
│   DYNAMODB (Cloud - AWS)                                                    │
│   ──────────────────────                                                    │
│   ┌─────────────┐     ┌─────────────┐                                      │
│   │   Python    │────▶│  DynamoDB   │  Fully managed by AWS                │
│   │   Script    │◀────│   (AWS)     │  Scales automatically                │
│   └─────────────┘     └─────────────┘  Has network latency                 │
│         │                   │                                              │
│         └─── Internet ──────┘                                              │
│                                                                             │
│                                                                             │
│   PERFORMANCE COMPARISON:                                                   │
│   ───────────────────────                                                   │
│                                                                             │
│   Store      │ p99 (100 entities)  │ Best For                              │
│   ───────────┼─────────────────────┼───────────────────────                │
│   SQLite     │ ~15ms               │ Local testing                         │
│   Redis      │ ~25ms               │ Production (low latency)              │
│   DynamoDB   │ ~150ms              │ Production (managed)                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature View Scaling Test

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FEATURE VIEW SCALING EXPLAINED                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   What is a Feature View?                                                   │
│   ───────────────────────                                                   │
│   A Feature View is a GROUP of related features.                            │
│                                                                             │
│   Example:                                                                  │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │                                                                │       │
│   │   Feature View: "user_profile"         Feature View: "purchases"      │
│   │   ├── name                             ├── total_spent                │
│   │   ├── age                              ├── last_purchase_date         │
│   │   ├── location                         ├── avg_order_value            │
│   │   └── signup_date                      └── purchase_count             │
│   │                                                                │       │
│   └────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│                                                                             │
│   Why does more Feature Views = slower?                                     │
│   ──────────────────────────────────────                                    │
│                                                                             │
│   1 Feature View:                                                           │
│   ┌──────────┐      1 query       ┌──────────┐                             │
│   │  Feast   │ ──────────────────▶│  Store   │  = Fast!                    │
│   └──────────┘                    └──────────┘                             │
│                                                                             │
│                                                                             │
│   10 Feature Views:                                                         │
│   ┌──────────┐      10 queries    ┌──────────┐                             │
│   │  Feast   │ ──────────────────▶│  Store   │  = 10x slower!              │
│   └──────────┘  (one per FV)      └──────────┘                             │
│                                                                             │
│                                                                             │
│   BENCHMARK RESULTS:                                                        │
│   ──────────────────                                                        │
│                                                                             │
│   Feature Views │  p99 Latency  │  SLA (60ms)                              │
│   ──────────────┼───────────────┼────────────                              │
│        1        │     45ms      │    ✅                                     │
│       10        │     81ms      │    ❌ (+80%)                              │
│       50        │    240ms      │    ❌ (+433%)                             │
│      100        │   ~450ms      │    ❌ (projected)                         │
│                                                                             │
│   KEY FINDING: Each Feature View adds ~4ms overhead                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Throughput Test (How Many Requests Per Second)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         THROUGHPUT TEST EXPLAINED                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   GOAL: Handle 3 Million requests per hour (production requirement)         │
│   ─────                                                                     │
│                                                                             │
│   3,000,000 requests/hour = 833 requests/second                             │
│                                                                             │
│                                                                             │
│   HOW WE TEST:                                                              │
│   ────────────                                                              │
│                                                                             │
│   We simulate many users hitting Feast at the same time:                    │
│                                                                             │
│   ┌──────────┐                                                              │
│   │ Worker 1 │──┐                                                           │
│   └──────────┘  │                                                           │
│   ┌──────────┐  │      ┌─────────────┐                                     │
│   │ Worker 2 │──┼─────▶│    FEAST    │                                     │
│   └──────────┘  │      │             │                                     │
│   ┌──────────┐  │      │  Count how  │                                     │
│   │ Worker 3 │──┼─────▶│  many req/s │                                     │
│   └──────────┘  │      │  it handles │                                     │
│       ...       │      └─────────────┘                                     │
│   ┌──────────┐  │                                                           │
│   │ Worker N │──┘                                                           │
│   └──────────┘                                                              │
│                                                                             │
│                                                                             │
│   RESULTS:                                                                  │
│   ────────                                                                  │
│                                                                             │
│   Workers │  RPS   │   RPH      │ Target (3M)                               │
│   ────────┼────────┼────────────┼────────────                               │
│      1    │  120   │   432,000  │   14%                                     │
│      5    │  118   │   424,800  │   14%                                     │
│     10    │  115   │   414,000  │   14%                                     │
│     20    │  110   │   396,000  │   13%                                     │
│                                                                             │
│   KEY FINDING: More workers doesn't help!                                   │
│   The bottleneck is in the SDK (Python code), not the infrastructure.       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Workflow Command Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COMMAND FLOW - WHAT HAPPENS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   YOU RUN:                                                                  │
│   ────────                                                                  │
│   $ python unified_benchmark.py --preset quick --store sqlite               │
│                                                                             │
│                                                                             │
│   WHAT HAPPENS INSIDE:                                                      │
│   ────────────────────                                                      │
│                                                                             │
│   1. Parse arguments                                                        │
│      └── preset=quick, store=sqlite                                         │
│                                                                             │
│   2. Create test data                                                       │
│      └── 500 users × 200 features → features.parquet                        │
│                                                                             │
│   3. Configure Feast                                                        │
│      └── Create feature_store.yaml with SQLite                              │
│                                                                             │
│   4. Materialize data                                                       │
│      └── Load parquet → SQLite database                                     │
│                                                                             │
│   5. Run latency tests                                                      │
│      ├── 50f × 1e → measure 20 times → calculate p50/p95/p99               │
│      ├── 50f × 10e → measure 20 times → calculate p50/p95/p99              │
│      ├── 50f × 100e → measure 20 times → calculate p50/p95/p99             │
│      └── ... more combinations                                              │
│                                                                             │
│   6. Run FV scaling tests                                                   │
│      ├── 1 FV → measure latency                                            │
│      ├── 10 FVs → measure latency                                          │
│      └── 50 FVs → measure latency                                          │
│                                                                             │
│   7. Run throughput tests                                                   │
│      ├── 1 worker for 10s → count requests                                 │
│      ├── 5 workers for 10s → count requests                                │
│      └── ... more workers                                                   │
│                                                                             │
│   8. Save results                                                           │
│      ├── benchmark_results.json                                            │
│      ├── benchmark_summary.csv                                             │
│      ├── benchmark_report.md                                               │
│      └── *.png charts                                                      │
│                                                                             │
│   9. Print summary                                                          │
│      └── "BENCHMARK COMPLETE - Results: results/"                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference - All Commands

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUICK REFERENCE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SETUP:                                                                    │
│   ──────                                                                    │
│   cd feast-benchmarking                                                     │
│   python3 -m venv venv                                                      │
│   source venv/bin/activate                                                  │
│   pip install -r requirements.txt                                           │
│                                                                             │
│                                                                             │
│   RUN BENCHMARKS:                                                           │
│   ────────────────                                                          │
│   # Quick test (2 min)                                                      │
│   python unified_benchmark.py --preset quick --store sqlite                 │
│                                                                             │
│   # Full test (30 min)                                                      │
│   python unified_benchmark.py --preset full --store redis                   │
│                                                                             │
│   # Custom test                                                             │
│   python unified_benchmark.py \                                             │
│       --features 50 200 \                                                   │
│       --entities 1 10 100 \                                                 │
│       --store sqlite                                                        │
│                                                                             │
│                                                                             │
│   VIEW RESULTS:                                                             │
│   ─────────────                                                             │
│   cat results_sqlite/benchmark_report.md                                    │
│   open results_sqlite/*.png                                                 │
│                                                                             │
│                                                                             │
│   COMPARE STORES:                                                           │
│   ────────────────                                                          │
│   python compare_stores.py \                                                │
│       --dirs results_sqlite results_redis \                                 │
│       --names sqlite redis \                                                │
│       --output comparison                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUMMARY                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   WHAT WE MEASURE:                                                          │
│   • Latency (p50, p95, p99) - how fast requests complete                   │
│   • Throughput (RPS, RPH) - how many requests per second                   │
│   • Function breakdown - where time is spent                               │
│   • Scaling behavior - how performance changes with load                   │
│                                                                             │
│   WHY WE MEASURE:                                                           │
│   • Ensure we meet SLA (60ms p99)                                          │
│   • Identify bottlenecks (SDK vs Store)                                    │
│   • Compare different configurations                                       │
│   • Validate fixes and optimizations                                       │
│                                                                             │
│   KEY FINDINGS SO FAR:                                                      │
│   • SDK bottleneck: protobuf conversion takes 35-40% of time              │
│   • Feature View scaling: each FV adds ~4ms overhead                       │
│   • Throughput limited: ~400K RPH (14% of 3M target)                      │
│   • More workers don't help (CPU-bound, not I/O-bound)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
