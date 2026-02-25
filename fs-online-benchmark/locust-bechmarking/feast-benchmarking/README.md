# Feast Online Store Benchmark Suite

Performance benchmarking framework for Feast online stores (SQLite, Redis, PostgreSQL, DynamoDB).

## Quick Start

```bash
# Run all stores with defaults
./run_full_benchmark.sh

# Dry run to see commands
./run_full_benchmark.sh --dry-run --verbose
```

## Directory Structure

```
feast-benchmarking/
├── run_full_benchmark.sh     # Main entry point - runs all benchmarks
├── unified_benchmark.py      # Python benchmark implementation
├── generate_charts.py        # Chart generation from results
├── k8s/                      # Kubernetes deployment
│   ├── base/                 # Base kustomize configs
│   ├── jobs/                 # Benchmark job definitions
│   ├── overlays/             # Environment-specific configs
│   └── stores/               # Redis/Postgres deployments
└── results/                  # Benchmark results
    ├── sqlite/
    ├── redis/
    ├── postgres/
    ├── dynamodb/
    └── charts/               # Generated PNG charts
```

## Usage

### Full Benchmark (All Stores)

```bash
./run_full_benchmark.sh
```

### Specific Stores Only

```bash
./run_full_benchmark.sh --stores "redis postgres"
```

### Custom Configuration

```bash
./run_full_benchmark.sh \
    --stores "sqlite redis postgres dynamodb" \
    --features 200 \
    --entities "1 10 50 100 200 500" \
    --iterations 100 \
    --warmup 10 \
    --namespace feast-benchmark
```

### All Options

| Option | Default | Description |
|--------|---------|-------------|
| `--stores` | `"sqlite redis postgres dynamodb"` | Stores to benchmark |
| `--namespace` | `feast-benchmark` | Kubernetes namespace |
| `--features` | `200` | Number of features |
| `--entities` | `"1 10 50 100 200 500"` | Entity counts to test |
| `--iterations` | `300` | Iterations per test (store-specific defaults apply) |
| `--warmup` | `20` | Warmup iterations (store-specific defaults apply) |
| `--timeout` | `1800` | Job timeout (seconds) |
| `--output-dir` | `results` | Results directory |
| `--skip-k8s` | `false` | Run SQLite locally only |
| `--skip-charts` | `false` | Skip chart generation |
| `--dry-run` | `false` | Preview commands |
| `--verbose` | `false` | Enable debug output |

## Prerequisites

- OpenShift/Kubernetes cluster with `oc` or `kubectl` CLI configured
- Python 3.11+
- AWS credentials (for DynamoDB benchmarks only)

---

## Complete Setup Guide

### Step 1: Clone the Repository

```bash
git clone -b perf-online-feat https://github.com/abhijeet-dhumal/featurestore-benchmarks.git
cd featurestore-benchmarks/fs-online-benchmark/locust-bechmarking/feast-benchmarking
```

### Step 2: Set Up Local Python Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Install dependencies
./.venv/bin/pip install feast matplotlib numpy pandas
```

### Step 3: Verify Kubernetes Access

```bash
# Check cluster connection
oc cluster-info

# Or with kubectl
kubectl cluster-info
```

### Step 4: Deploy Infrastructure on Kubernetes

```bash
# Create namespace and base resources (PVC, ConfigMaps)
oc apply -k k8s/base

# Deploy Redis and PostgreSQL
oc apply -k k8s/stores

# Wait for pods to be ready
oc wait --for=condition=ready pod -l app=redis -n feast-benchmark --timeout=120s
oc wait --for=condition=ready pod -l app=postgres -n feast-benchmark --timeout=120s

# Verify deployments
oc get pods -n feast-benchmark
```

### Step 5: Configure AWS Credentials (DynamoDB Only)

```bash
# Skip this step if not benchmarking DynamoDB
oc create secret generic aws-credentials \
    -n feast-benchmark \
    --from-literal=AWS_ACCESS_KEY_ID=<your-key> \
    --from-literal=AWS_SECRET_ACCESS_KEY=<your-secret> \
    --from-literal=AWS_DEFAULT_REGION=us-east-1
```

### Step 6: Run the Automated Benchmark

```bash
# Full benchmark (all 4 stores)
./run_full_benchmark.sh

# Or specific stores only
./run_full_benchmark.sh --stores "redis postgres"

# Preview commands without executing
./run_full_benchmark.sh --dry-run --verbose
```

### Step 7: View Results

```bash
# Results are saved to:
ls -la results/sqlite/benchmark_results.json
ls -la results/redis/benchmark_results.json
ls -la results/postgres/benchmark_results.json
ls -la results/dynamodb/benchmark_results.json

# Charts are generated in:
ls -la results/charts/
```

---

## What the Script Does

The `run_full_benchmark.sh` script automates the entire process:

1. **Validates prerequisites** - checks cluster access, namespace, Python env
2. **Cleans up old jobs** - removes previous benchmark jobs
3. **Creates benchmark jobs** - one K8s Job per store (Redis, Postgres, DynamoDB)
4. **Runs SQLite locally** - SQLite doesn't need K8s infrastructure
5. **Waits for completion** - monitors job status until done or timeout
6. **Collects results** - copies JSON results from PVC to local `results/` dir
7. **Generates charts** - creates 11 PNG visualizations in `results/charts/`

---

## Benchmark Configuration

### Optimizations Applied

All benchmarks run with these optimizations:

| Optimization | Setting | Purpose |
|--------------|---------|---------|
| Registry Cache | `cache_ttl_seconds: 0` | Infinite cache |
| Serialization | `entity_key_serialization_version: 3` | Latest format |
| Registry Pre-warm | `fs.refresh_registry()` | Pre-populate cache |
| DynamoDB Pool | `max_pool_connections: 200` | Connection reuse |
| DynamoDB Retry | `retry_mode: adaptive` | Intelligent retry |

### Test Matrix

| Dimension | Values |
|-----------|--------|
| Features | 200 |
| Entities | 1, 10, 50, 100, 200, 500 |
| Stores | SQLite, Redis, PostgreSQL, DynamoDB |
| Iterations | 300 (increased for reliability) |
| Warmup | 20 (increased for stability) |

### Reliability Metrics

Results now include **Coefficient of Variation (CV)** to assess measurement reliability:

| CV | Status | Meaning |
|----|--------|---------|
| < 15% | ✓ Good | Reliable measurement |
| 15-25% | ⚠ Warning | Moderate variance |
| > 25% | ✗ Poor | High variance, re-run recommended |

**Target: CV < 15%** for production-quality benchmarks.

## Results

### Latest Benchmark (200 features, p99 latency) - Feb 25, 2026

| Entities | SQLite | Redis | Postgres | DynamoDB | SLA (60ms) |
|----------|--------|-------|----------|----------|------------|
| 1 | 17ms | 19ms | **15ms** | 34ms | ✅ |
| 10 | **76ms** | 94ms | 79ms | 119ms | ❌ |
| 50 | **149ms** | 156ms | 216ms | 229ms | ❌ |
| 100 | 241ms | **229ms** | 297ms | 338ms | ❌ |
| 200 | 463ms | **417ms** | 586ms | 643ms | ❌ |
| 500 | **1041ms** | 1053ms | 1369ms | 1541ms | ❌ |

**Ranking (@ 50 entities):** SQLite (149ms) > Redis (156ms) > Postgres (216ms) > DynamoDB (229ms)

**Production Target (50 entities × 200 features):**
- Best: SQLite 149ms (2.5x over SLA)
- Worst: DynamoDB 229ms (3.8x over SLA)
- All stores FAIL 60ms SLA at 10+ entities

**Key Finding:** Bottleneck is Python SDK overhead (40-80% of time), NOT database reads.

### Generated Charts

After running benchmarks, 11 charts are saved to `results/charts/`:

**Benchmark Charts (01-07):**

| Chart | Description |
|-------|-------------|
| `01_latency_by_entities.png` | P99 latency grouped by entity count |
| `02_scaling_curves.png` | Log-log scaling behavior (O(n) proof) |
| `03_store_ranking.png` | Store ranking at key entity counts |
| `04_time_breakdown.png` | Stacked bar: where time is spent (from profiling) |
| `05_sla_gap_analysis.png` | Multiplier vs 60ms target |
| `06_executive_summary.png` | 4-panel summary (50 entities target) |
| `07_production_sla.png` | Production SLA analysis (50 & 200 entities) |

**Bottleneck Analysis Charts (08-11):**

| Chart | Description |
|-------|-------------|
| `08_bottleneck_breakdown.png` | Top functions by time per store |
| `09_category_comparison.png` | Grouped bars comparing categories across stores |
| `10_optimization_waterfall.png` | Cumulative time breakdown per store |
| `11_function_heatmap.png` | Cross-store function time comparison |

## Manual Commands

### Run Individual Store

```bash
# SQLite
oc create -f k8s/jobs/sqlite-job.yaml -n feast-benchmark

# Redis
oc create -f k8s/jobs/redis-job.yaml -n feast-benchmark

# PostgreSQL
oc create -f k8s/jobs/postgres-job.yaml -n feast-benchmark

# DynamoDB
oc create -f k8s/jobs/dynamodb-job.yaml -n feast-benchmark
```

### Fetch Results

```bash
# Create results reader pod
oc run results-reader -n feast-benchmark --image=busybox --restart=Never \
    --overrides='{"spec":{"containers":[{"name":"results-reader","image":"busybox","command":["sleep","3600"],"volumeMounts":[{"name":"results","mountPath":"/results"}]}],"volumes":[{"name":"results","persistentVolumeClaim":{"claimName":"benchmark-results"}}]}}'

# Get results
oc exec results-reader -n feast-benchmark -- cat /results/redis/benchmark_results.json

# Cleanup
oc delete pod results-reader -n feast-benchmark
```

### Generate Charts

```bash
./.venv/bin/python generate_charts.py \
    --dirs results/sqlite results/redis results/postgres results/dynamodb \
    --names sqlite redis postgres dynamodb \
    --output results/charts
```

### Function-Level Profiling

For detailed breakdown of where time is spent at the function level:

```bash
# Run bottleneck analyzer (profiles all stores)
./.venv/bin/python analyze_bottlenecks.py --entities 50 --features 200 --iterations 10

# Results saved to: results/profile/bottleneck_analysis.json
```

The profiling data is automatically used by charts 04, 08-11 to show accurate time breakdown by category:
- **DB/Store Read**: Time in online_read(), database queries
- **Protobuf/Serialization**: MessageToDict, _convert_rows_to_protobuf
- **Timestamp Handling**: FromDatetime, convert_timestamp
- **Type Checking**: isinstance, validation
- **Other**: Miscellaneous overhead

**Note:** Charts 08-11 require profiling data. Run `analyze_bottlenecks.py` first, or the charts will use estimated values.

## Troubleshooting

### Job Failed

```bash
# Check pod logs
oc logs -n feast-benchmark -l store=redis

# Check job status
oc describe job feast-benchmark-redis -n feast-benchmark
```

### AWS Credentials Missing

```bash
# Verify secret exists
oc get secret aws-credentials -n feast-benchmark
```

### Results Not Found

```bash
# Check PVC
oc get pvc benchmark-results -n feast-benchmark

# List available results
oc exec results-reader -n feast-benchmark -- ls -la /results/
```

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `PERFORMANCE_ASSESSMENT.md` | Full performance analysis with findings and recommendations |
| `BENCHMARK_STATUS.md` | Current project status and JIRA alignment |
| `NEXT_ACTIONS.md` | Prioritized task list for next implementation steps |
| `results/charts/README.md` | Detailed chart descriptions and interpretation guide |
| `k8s/README.md` | Kubernetes deployment guide |

## JIRA Tracking

| Ticket | Summary | Status |
|--------|---------|--------|
| [RHOAIENG-46061](https://issues.redhat.com/browse/RHOAIENG-46061) | Epic: Performance Optimization | New |
| [RHOAIENG-50008](https://issues.redhat.com/browse/RHOAIENG-50008) | Test harness setup | 80% |
| [RHOAIENG-50010](https://issues.redhat.com/browse/RHOAIENG-50010) | Baseline benchmarks | 70% |
| [RHOAIENG-50013](https://issues.redhat.com/browse/RHOAIENG-50013) | Bottleneck identification | In Progress |

## PRs Submitted to Feast

| PR | Fix | Status |
|----|-----|--------|
| [#6003](https://github.com/feast-dev/feast/pull/6003) | Timestamp conversion O(n×m) → O(n) | Pending review |
| [#6006](https://github.com/feast-dev/feast/pull/6006) | Entity key serialization dedup | Pending review |
| [#6014](https://github.com/feast-dev/feast/pull/6014) | Registry lookup optimization | Pending review |
| [#6015](https://github.com/feast-dev/feast/pull/6015) | MessageToDict optimization (~4x faster) | Pending review |
