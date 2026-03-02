# Feast Online Store Benchmark Suite

Performance benchmarking framework for Feast online stores (SQLite, Redis, PostgreSQL, DynamoDB).

> **📊 [View Full Benchmark Results →](fs-online-benchmark/locust-bechmarking/feast-benchmarking/README.md)**

## Quick Start

```bash
# Run all stores with defaults
./run_full_benchmark.sh

# Compare multiple Feast versions
./run_full_benchmark.sh --compare

# Dry run to preview commands
./run_full_benchmark.sh --dry-run --verbose
```

## Results Summary

| Store | v0.60.0 | Optimized | Improvement |
|-------|---------|-----------|-------------|
| Redis | 148ms | **103ms** | **30%** |
| SQLite | 157ms | **109ms** | **31%** |
| PostgreSQL | 167ms | **124ms** | **26%** |
| DynamoDB | 217ms | **164ms** | **25%** |

*P99 latency @ 50 entities × 200 features. See [README.md](README.md) for details.*

---

## Script Options

| Option | Default | Description |
|--------|---------|-------------|
| `--stores <list>` | `"sqlite redis postgres dynamodb"` | Stores to benchmark |
| `--scenario <name>` | `all` | `entity_scaling`, `feature_scaling`, or `all` |
| `--compare` | - | Compare all refs in config |
| `--refs <list>` | - | Specific refs (e.g., `"v0.60.0,master"`) |
| `--feast-git-ref <ref>` | - | Custom Feast branch/tag |
| `--stage <stage>` | `all` | `build`, `benchmark`, `charts`, or `all` |
| `--dry-run` | - | Preview without executing |
| `--help` | - | Show all options |

### Full Command Example (All Options)

```bash
./run_full_benchmark.sh \
    --config benchmark.config.yaml \
    --stores "sqlite redis postgres dynamodb" \
    --namespace feast-benchmark \
    --output-dir results \
    --features 200 \
    --entities "1 10 50 100 200 500" \
    --iterations 300 \
    --warmup 20 \
    --timeout 1800 \
    --scenario all \
    --compare \
    --refs "v0.60.0,master,optimized" \
    --feast-git-ref master \
    --feast-git-url https://github.com/feast-dev/feast.git \
    --base-image quay.io/user/feast-benchmark-base:latest \
    --stage all \
    --verbose
```

### Common Examples

```bash
# Test custom branch
./run_full_benchmark.sh --feast-git-ref perf/my-optimization

# Redis and Postgres only
./run_full_benchmark.sh --stores "redis postgres"

# Generate charts only (no K8s)
./run_full_benchmark.sh --compare --stage charts

# Run locally (SQLite only, no K8s)
./run_full_benchmark.sh --skip-k8s --stores sqlite
```

---

## Setup

### Prerequisites

- OpenShift/Kubernetes cluster with `oc` or `kubectl`
- Python 3.11+
- AWS credentials (for DynamoDB only)

### Deploy Infrastructure

```bash
# Clone
git clone -b perf-online-feat https://github.com/abhijeet-dhumal/featurestore-benchmarks.git
cd featurestore-benchmarks/fs-online-benchmark/locust-bechmarking/feast-benchmarking

# Setup Python
python3 -m venv .venv && ./.venv/bin/pip install feast matplotlib numpy pandas

# Deploy K8s resources
oc apply -k k8s/base
oc apply -k k8s/stores

# (Optional) AWS credentials for DynamoDB
oc create secret generic aws-credentials -n feast-benchmark \
    --from-literal=AWS_ACCESS_KEY_ID=<key> \
    --from-literal=AWS_SECRET_ACCESS_KEY=<secret>
```

---

## Directory Structure

```
feast-benchmarking/
├── run_full_benchmark.sh     # Main automation script
├── scripts/                  # Python benchmark & chart scripts
├── k8s/                      # Kubernetes manifests
└── results/                  # Output (per Git reference)
    ├── v0.60.0/charts/
    ├── master/charts/
    ├── optimized/charts/
    └── comparison/charts/    # Cross-reference comparison
```

---

## Generated Charts

| Chart | Description |
|-------|-------------|
| `01_latency_by_entities.png` | P99 by entity count |
| `01b_latency_by_features.png` | P99 by feature count |
| `02_production_sla.png` | SLA gap analysis |
| `03_executive_summary.png` | 4-panel overview |
| `05_bottleneck_breakdown.png` | Function-level profiling |
| `01_cross_reference_comparison.png` | Multi-version comparison |

---

## PRs Submitted to Feast

| PR | Improvement | Impact | Status |
|----|-------------|--------|--------|
| [#6003](https://github.com/feast-dev/feast/pull/6003) | Timestamp O(n×m) → O(n) | -5 to -10ms | Open |
| [#6006](https://github.com/feast-dev/feast/pull/6006) | Entity key deduplication | -3 to -5ms | ✅ Merged |
| [#6014](https://github.com/feast-dev/feast/pull/6014) | Registry N+1 fix | -1 to -2ms | ✅ Merged |
| [#6015](https://github.com/feast-dev/feast/pull/6015) | MessageToDict 4x faster | -5 to -15ms | Open |
| [#6023](https://github.com/feast-dev/feast/pull/6023) | Redis protobuf parsing | -2 to -5ms | ✅ Merged |
| [#6024](https://github.com/feast-dev/feast/pull/6024) | DynamoDB parallel batches | -40 to -120ms | Open |

---

## Troubleshooting

```bash
# Check job logs
oc logs -n feast-benchmark -l store=redis

# Check job status
oc describe job feast-benchmark-redis -n feast-benchmark

# Verify AWS credentials
oc get secret aws-credentials -n feast-benchmark
```
