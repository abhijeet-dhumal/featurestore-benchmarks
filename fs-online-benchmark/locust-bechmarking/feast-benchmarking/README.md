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
├── .gitignore                    # Git ignore rules
│
├── unified_benchmark.py          # Main benchmark script
├── generate_charts.py            # Curated chart generator (4 charts)
├── compare_stores.py             # Multi-store comparison tool
├── benchmark_config.py           # Configuration presets
├── run_all_benchmarks.sh         # Automated runner script
│
├── common/                       # Shared utilities
│   ├── __init__.py
│   └── stop_watch.py
│
├── k8s/                          # Kubernetes manifests
│   ├── README.md                 # K8s deployment guide
│   ├── 00-namespace.yaml         # Namespace definition
│   ├── 01-redis.yaml             # Redis deployment
│   ├── 03-aws-secret.yaml        # AWS credentials template
│   ├── 04-postgres.yaml          # PostgreSQL deployment
│   └── jobs/                     # Benchmark job manifests
│       ├── sqlite.yaml
│       ├── redis.yaml
│       ├── dynamodb.yaml
│       └── postgres.yaml
│
├── results/                      # Benchmark results (tracked in git)
│   ├── sqlite/                   # SQLite results
│   ├── redis/                    # Redis results
│   ├── dynamodb/                 # DynamoDB results
│   ├── postgres/                 # PostgreSQL results
│   └── comparison/               # Cross-store comparison charts
│
├── docs/                         # Documentation
│   └── WORKFLOW_EXPLAINED.md     # Visual workflow guide
│
└── deprecated/                   # Legacy scripts (reference only)
    ├── comprehensive_benchmark.py
    ├── extended_benchmark.py
    ├── locustfile_feast.py
    └── setup_feast_benchmark.py
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

Each benchmark run produces raw data only (no charts):

```
results/<store>/
├── benchmark_results.json        # Raw results (JSON)
├── benchmark_summary.csv         # Summary table (CSV)
└── benchmark_report.md           # Human-readable report
```

Comparison charts (generated via `generate_charts.py`):
```
results/comparison/
├── 01_latency_comparison.png     # P99 latency by entity count
├── 02_scaling_behavior.png       # Scaling from min to max entities
├── 03_bottleneck_breakdown.png   # Request time breakdown
└── 04_sla_compliance.png         # SLA pass/fail status
```

## Kubernetes Deployment

See `k8s/README.md` for in-cluster benchmark deployment.

```bash
# Deploy namespace
kubectl apply -f k8s/00-namespace.yaml

# Deploy online stores
kubectl apply -f k8s/01-redis.yaml       # Redis
kubectl apply -f k8s/04-postgres.yaml    # PostgreSQL

# Run benchmark jobs
kubectl apply -f k8s/jobs/redis.yaml
kubectl apply -f k8s/jobs/postgres.yaml
kubectl apply -f k8s/jobs/dynamodb.yaml  # Requires AWS secret (k8s/03-aws-secret.yaml)

# View results
kubectl logs -f job/feast-benchmark-redis -n feast-test
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
