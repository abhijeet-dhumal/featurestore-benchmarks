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
| `--iterations` | `100` | Iterations per test |
| `--warmup` | `10` | Warmup iterations |
| `--timeout` | `900` | Job timeout (seconds) |
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
7. **Generates charts** - creates 10 PNG visualizations in `results/charts/`

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
| Iterations | 100 |
| Warmup | 10 |

## Results

### Latest Benchmark (200 features, p99 latency)

| Entities | SQLite | Redis | Postgres | DynamoDB | SLA (60ms) |
|----------|--------|-------|----------|----------|------------|
| 1 | 15ms | **15ms** | 60ms | 22ms | ✅ |
| 10 | 93ms | **74ms** | 80ms | 116ms | ❌ |
| 50 | 166ms | **142ms** | 157ms | 192ms | ❌ |
| 100 | 254ms | **202ms** | 354ms | 311ms | ❌ |
| 500 | 1104ms | **989ms** | 1322ms | 1438ms | ❌ |

**Ranking:** Redis > SQLite > Postgres > DynamoDB

### Generated Charts

After running benchmarks, 8 charts are saved to `results/charts/`:

| Chart | Description |
|-------|-------------|
| `01_latency_by_entities.png` | P99 latency grouped by entity count |
| `02_scaling_curves.png` | Log-log scaling behavior |
| `03_store_ranking.png` | Store ranking at key entity counts |
| `04_time_breakdown.png` | Stacked bar: where time is spent |
| `05_sla_gap_analysis.png` | Multiplier vs 60ms target |
| `06_executive_summary.png` | 4-panel summary |
| `07_production_sla.png` | Production SLA analysis (50 & 200 entities) |
| `08_time_distribution.png` | Donut charts by component (actual data) |

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
# Profile at 200 entities, 200 features
./.venv/bin/python profile_breakdown.py --entities 200 --features 200 --iterations 10

# Save results to JSON
./.venv/bin/python profile_breakdown.py --entities 200 --features 200 --output results/profile.json
```

This uses cProfile to identify exactly which functions consume time (useful for optimization).

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
