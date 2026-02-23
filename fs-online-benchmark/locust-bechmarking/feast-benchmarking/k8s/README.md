# Kubernetes Manifests for Feast Benchmarking

Ready-to-use Kubernetes manifests for running Feast benchmarks in a cluster.

## Files

| File | Description |
|------|-------------|
| `00-namespace.yaml` | Creates `feast-benchmark` namespace |
| `01-redis.yaml` | Redis deployment and service |
| `02-postgres.yaml` | PostgreSQL deployment, service, and secret |
| `03-aws-secret.yaml` | AWS credentials template for DynamoDB |
| `10-benchmark-job-sqlite.yaml` | SQLite benchmark job |
| `11-benchmark-job-redis.yaml` | Redis benchmark job |
| `12-benchmark-job-dynamodb.yaml` | DynamoDB benchmark job |

## Quick Start

### 1. Create Namespace

```bash
kubectl apply -f 00-namespace.yaml
```

### 2. Deploy Infrastructure

```bash
# Redis
kubectl apply -f 01-redis.yaml
kubectl wait --for=condition=available deployment/redis -n feast-benchmark --timeout=120s

# PostgreSQL (optional)
kubectl apply -f 02-postgres.yaml
kubectl wait --for=condition=available deployment/postgres -n feast-benchmark --timeout=120s

# DynamoDB (requires AWS credentials)
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
envsubst < 03-aws-secret.yaml | kubectl apply -f -
```

### 3. Run Benchmarks

```bash
# SQLite (no dependencies)
kubectl apply -f 10-benchmark-job-sqlite.yaml
kubectl logs -f job/feast-benchmark-sqlite -n feast-benchmark

# Redis (requires Redis running)
kubectl apply -f 11-benchmark-job-redis.yaml
kubectl logs -f job/feast-benchmark-redis -n feast-benchmark

# DynamoDB (requires AWS secret)
kubectl apply -f 12-benchmark-job-dynamodb.yaml
kubectl logs -f job/feast-benchmark-dynamodb -n feast-benchmark
```

### 4. View Results

```bash
# Check job status
kubectl get jobs -n feast-benchmark

# Get results from pod
POD=$(kubectl get pods -n feast-benchmark -l store=sqlite -o jsonpath='{.items[0].metadata.name}')
kubectl cp feast-benchmark/$POD:/results/benchmark_sqlite.json ./results_sqlite.json
```

### 5. Cleanup

```bash
# Delete jobs
kubectl delete jobs -n feast-benchmark --all

# Delete infrastructure
kubectl delete -f 01-redis.yaml
kubectl delete -f 02-postgres.yaml

# Delete namespace (removes everything)
kubectl delete namespace feast-benchmark
```

## Run All Benchmarks

```bash
#!/bin/bash
# run_all_k8s_benchmarks.sh

set -e

# Setup
kubectl apply -f 00-namespace.yaml
kubectl apply -f 01-redis.yaml
kubectl wait --for=condition=available deployment/redis -n feast-benchmark --timeout=120s

# Run benchmarks
echo "=== SQLite Benchmark ==="
kubectl apply -f 10-benchmark-job-sqlite.yaml
kubectl wait --for=condition=complete job/feast-benchmark-sqlite -n feast-benchmark --timeout=600s

echo "=== Redis Benchmark ==="
kubectl apply -f 11-benchmark-job-redis.yaml
kubectl wait --for=condition=complete job/feast-benchmark-redis -n feast-benchmark --timeout=600s

# Export results
mkdir -p results
for store in sqlite redis; do
  POD=$(kubectl get pods -n feast-benchmark -l store=$store -o jsonpath='{.items[0].metadata.name}')
  kubectl cp feast-benchmark/$POD:/results/benchmark_${store}.json ./results/
done

echo "=== Results ==="
ls -la results/
```

## OpenShift Notes

For OpenShift clusters:

```bash
# Use oc instead of kubectl
oc apply -f 00-namespace.yaml

# Grant permissions if needed
oc adm policy add-scc-to-user anyuid -z default -n feast-benchmark
```

## Customizing Benchmark Parameters

Edit the job YAML to change:

- `NUM_ENTITIES`: Number of test entities (default: 500)
- `NUM_FEATURES`: Number of features (default: 200)
- Entity/feature combinations in the benchmark loop
- Iteration count (default: 20)

Example modification in the job script:

```python
# Test different configurations
for num_entities in [1, 10, 50, 100, 500, 1000]:  # Added 1000
    for num_features in [50, 100, 200]:  # Added 100
        ...
```
