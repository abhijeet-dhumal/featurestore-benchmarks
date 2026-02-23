# Feast Performance Benchmark Suite

Comprehensive benchmark framework for evaluating Feast online feature serving performance.

**Target SLAs:**
- p99 Latency: **60ms**
- Throughput: **3M requests/hour**

## Directory Structure

```
feast-benchmarking/
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── run-benchmarks.sh             # One-command in-cluster orchestrator
│
├── unified_benchmark.py          # Local benchmark script
├── generate_charts.py            # Comparison chart generator (4 charts)
├── generate_profile_charts.py    # Profile chart generator (4 charts)
├── benchmark_config.py           # Configuration presets
│
├── common/                       # Shared utilities
│   ├── __init__.py
│   └── stop_watch.py
│
├── k8s/                          # Kubernetes manifests (Kustomize)
│   ├── base/                     # Base resources
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── results-pvc.yaml      # Shared PVC for results
│   │   └── configmap.yaml        # Benchmark settings
│   │
│   ├── stores/                   # Online store deployments
│   │   ├── kustomization.yaml
│   │   ├── redis.yaml
│   │   └── postgres.yaml
│   │
│   ├── jobs/                     # Benchmark jobs
│   │   ├── kustomization.yaml
│   │   ├── sqlite-job.yaml       # SQLite benchmark
│   │   ├── redis-job.yaml        # Redis benchmark
│   │   ├── postgres-job.yaml     # PostgreSQL benchmark
│   │   ├── dynamodb-job.yaml     # DynamoDB benchmark
│   │   ├── profile-job.yaml      # Deep profiling
│   │   └── collect-results.yaml  # Results aggregator
│   │
│   ├── overlays/                 # Environment-specific configs
│   │   ├── quick/                # Quick (10 iterations)
│   │   └── full/                 # Full (50 iterations)
│   │
│   └── legacy/                   # Old non-kustomize manifests
│
├── results/                      # Benchmark results
│   ├── cluster/                  # In-cluster benchmark results
│   │   ├── sqlite/
│   │   ├── redis/
│   │   ├── postgres/
│   │   ├── dynamodb/
│   │   ├── profile/
│   │   └── combined/             # Aggregated results
│   └── comparison/               # Generated charts
│
└── deprecated/                   # Legacy scripts
```

## Quick Start

### 1. Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Benchmarks

```bash
# SQLite (local, no dependencies)
python unified_benchmark.py --preset quick --store sqlite --output results/sqlite

# Redis (requires Redis server)
python unified_benchmark.py --preset quick \
    --store redis \
    --redis-host localhost \
    --redis-port 6379 \
    --output results/redis

# DynamoDB (requires AWS credentials)
python unified_benchmark.py --preset quick \
    --store dynamodb \
    --dynamodb-region eu-west-1 \
    --aws-access-key-id AKIAXXXX \
    --aws-secret-access-key XXXXXXXX \
    --output results/dynamodb

# PostgreSQL (requires PostgreSQL server)
python unified_benchmark.py --preset quick \
    --store postgres \
    --postgres-host localhost \
    --postgres-port 5432 \
    --postgres-database feast \
    --postgres-user feast \
    --postgres-password feast123 \
    --output results/postgres
```

### 3. Generate Comparison Charts

```bash
python generate_charts.py \
    --dirs results/sqlite results/redis results/dynamodb \
    --names sqlite redis dynamodb \
    --output results/comparison
```

This generates 4 curated charts optimized for sharing:
- `01_latency_comparison.png` - P99 latency grouped bars with SLA line
- `02_scaling_behavior.png` - Min to max entity scaling (slope chart)
- `03_bottleneck_breakdown.png` - Time breakdown waterfall
- `04_sla_compliance.png` - SLA pass/fail bullet chart

## Presets

| Preset | Description | Duration | Use Case |
|--------|-------------|----------|----------|
| `quick` | Minimal test matrix | ~2 min | Quick validation |
| `full` | Complete matrix | ~30 min | Full analysis |
| `production` | Production config | ~60 min | Production validation |

## CLI Reference

Run `python unified_benchmark.py --help` for full options. Key arguments:

**Store Selection:**
- `--store {sqlite,redis,dynamodb,postgres}` - Online store type

**Redis:**
- `--redis-host`, `--redis-port`, `--redis-password`, `--redis-ssl`

**DynamoDB:**
- `--dynamodb-region`, `--aws-access-key-id`, `--aws-secret-access-key`

**PostgreSQL:**
- `--postgres-host`, `--postgres-port`, `--postgres-database`, `--postgres-user`, `--postgres-password`

**Test Dimensions:**
- `--features N [N ...]` - Feature counts (default: 50 200)
- `--entities N [N ...]` - Entity counts (default: 1 10 50 100 500)
- `--fv-counts N [N ...]` - Feature View counts (default: 1 10 50)
- `--iterations N` - Iterations per test (default: 20)

**Skip Tests:**
- `--skip-latency`, `--skip-fv-scaling`, `--skip-transformations`, `--skip-throughput`

**SLA Targets:**
- `--sla-p99-ms MS` - p99 latency target (default: 60)
- `--sla-throughput-rph RPH` - Throughput target (default: 3000000)

## Output

### In-Cluster Results

```
results/cluster/
├── sqlite/benchmark_results.json
├── redis/benchmark_results.json
├── postgres/benchmark_results.json
├── dynamodb/benchmark_results.json
├── profile/deep_profile_results.json
└── combined/all_results.json     # Aggregated from all stores
```

### Generated Charts

**Comparison charts** (`generate_charts.py`):
```
results/comparison/
├── 01_latency_comparison.png     # P99 latency by entity count
├── 02_scaling_behavior.png       # Scaling from min to max entities
├── 03_bottleneck_breakdown.png   # Request time breakdown
└── 04_sla_compliance.png         # SLA pass/fail status
```

**Profile charts** (`generate_profile_charts.py` with `--profile`):
```
results/comparison/
├── 05_high_level_breakdown.png   # Time by Feast component
├── 06_online_read_breakdown.png  # Store-specific internals
├── 07_optimization_targets.png   # Potential savings
└── 08_time_distribution.png      # Pie charts per store
```

### Local Benchmark Output

```
results/<store>/
├── benchmark_results.json        # Raw results (JSON)
├── benchmark_summary.csv         # Summary table (CSV)
└── benchmark_report.md           # Human-readable report
```

## Fully Automated Benchmarks

**One command runs everything and generates charts:**

```bash
# Production scale (200 features × 500 entities)
./run-benchmarks.sh production

# Quick validation (50 features × 100 entities)
./run-benchmarks.sh quick

# Full analysis (200 features × 1000 entities)
./run-benchmarks.sh full

# Skip DynamoDB (no AWS credentials needed)
./run-benchmarks.sh production --skip-dynamodb

# Regenerate charts only (from existing results)
./run-benchmarks.sh --charts-only

# Clean up all resources
./run-benchmarks.sh --cleanup
```

### What It Does Automatically

1. **Deploys infrastructure** - Namespace, NFS PVC, ConfigMap
2. **Deploys stores** - Redis, PostgreSQL (waits until ready)
3. **Copies AWS credentials** - From `feast-test` namespace if available
4. **Runs benchmarks** - SQLite, Redis, PostgreSQL, DynamoDB, Profiling
5. **Waits for completion** - Monitors all jobs
6. **Copies results** - From cluster PVC to local `results/<overlay>/`
7. **Generates charts** - All 8 comparison and profile charts

### Overlays

| Overlay | Features | Entities | Iterations | Duration |
|---------|----------|----------|------------|----------|
| `quick` | 50 | 1,10,100 | 10 | ~3 min |
| `production` | 200 | 1,10,100,500 | 20 | ~10 min |
| `full` | 200 | 1-1000 | 50 | ~30 min |

### Output

```
results/
├── production/           # Benchmark results by overlay
│   ├── sqlite/
│   ├── redis/
│   ├── postgres/
│   ├── dynamodb/
│   └── profile/
└── comparison/           # Generated charts (all 8)
    ├── 01_latency_comparison.png
    ├── 02_scaling_behavior.png
    ├── 03_bottleneck_breakdown.png
    ├── 04_sla_compliance.png
    ├── 05_high_level_breakdown.png
    ├── 06_online_read_breakdown.png
    ├── 07_optimization_targets.png
    └── 08_time_distribution.png
```

### Prerequisites

- `kubectl` configured with cluster access
- `nfs-csi` StorageClass (or modify `k8s/base/results-pvc.yaml`)
- Python 3 (for chart generation)
- For DynamoDB: `aws-credentials` secret in `feast-test` namespace

### Manual Kustomize (if needed)

```bash
# Deploy infrastructure only
kubectl apply -k k8s/overlays/production

# Apply jobs manually
kubectl apply -f k8s/jobs/sqlite-job.yaml -n feast-benchmark
kubectl apply -f k8s/jobs/redis-job.yaml -n feast-benchmark
# etc.
```

## Environment Variables

All store configs can be set via environment variables:

```bash
# AWS/DynamoDB
export AWS_ACCESS_KEY_ID=AKIAXXXX
export AWS_SECRET_ACCESS_KEY=XXXXXXXX
export AWS_DEFAULT_REGION=us-east-1

# Redis
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=mypassword

# PostgreSQL
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=feast
export POSTGRES_USER=feast
export POSTGRES_PASSWORD=feast123
```
