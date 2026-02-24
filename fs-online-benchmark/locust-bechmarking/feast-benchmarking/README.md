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

### Kubernetes Cluster

```bash
# Verify cluster connection
oc cluster-info

# Create namespace and infrastructure
oc apply -k k8s/base
oc apply -k k8s/stores
```

### AWS Credentials (for DynamoDB)

```bash
# Create secret
oc create secret generic aws-credentials \
    -n feast-benchmark \
    --from-literal=AWS_ACCESS_KEY_ID=<key> \
    --from-literal=AWS_SECRET_ACCESS_KEY=<secret> \
    --from-literal=AWS_DEFAULT_REGION=<region>
```

### Local Environment

```bash
# Python 3.11+ required
python3 -m venv .venv
./.venv/bin/pip install feast matplotlib numpy pandas
```

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

After running benchmarks, charts are saved to `results/charts/`:

- `01_latency_comparison.png` - P99 latency by entity count
- `02_scaling_behavior.png` - Scaling curves
- `03_bottleneck_breakdown.png` - Time breakdown
- `04_sla_compliance.png` - SLA pass/fail
- `05_sla_boundary.png` - SLA boundary analysis
- `06_statefarm_sla.png` - State Farm requirements

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
