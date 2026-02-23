# Kubernetes Manifests for Feast Benchmarking

Kustomize-based Kubernetes manifests for running Feast benchmarks in a cluster.

## Structure

```
k8s/
├── base/                    # Base resources (namespace, configmap, PVC)
├── stores/                  # Store deployments (Redis, Postgres)
├── jobs/                    # Benchmark jobs (per store)
├── overlays/
│   ├── quick/              # Quick smoke test
│   ├── full/               # Full matrix test
│   ├── production/         # Production-like config
│   └── statefarm/          # State Farm SLA requirements
└── legacy/                  # Old standalone files
```

## Overlay Configurations

| Overlay | Entities | Features | Iterations | Use Case |
|---------|----------|----------|------------|----------|
| `quick` | 1,10,100 | 50 | 10 | Fast validation |
| `full` | 1,10,50,100,200,500 | 10,50,100,200 | 20 | Complete matrix |
| `production` | 1,10,50,100,200,500 | 200 | 30 | Production-like |
| `statefarm` | **50,200** | **200** | **50** | State Farm SLA (60ms) |

## Quick Start

### 1. Deploy Infrastructure (State Farm config)

```bash
# Apply State Farm overlay (namespace, configmap, stores)
kubectl apply -k k8s/overlays/statefarm

# Wait for stores to be ready
kubectl wait --for=condition=available deployment/redis -n feast-benchmark --timeout=120s
kubectl wait --for=condition=available deployment/postgres -n feast-benchmark --timeout=120s
```

### 2. Run Benchmarks

```bash
# Redis benchmark
kubectl apply -f k8s/jobs/redis-job.yaml
kubectl logs -f job/feast-benchmark-redis -n feast-benchmark

# PostgreSQL benchmark
kubectl apply -f k8s/jobs/postgres-job.yaml
kubectl logs -f job/feast-benchmark-postgres -n feast-benchmark

# DynamoDB (requires AWS credentials)
kubectl create secret generic aws-credentials -n feast-benchmark \
  --from-literal=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  --from-literal=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  --from-literal=AWS_DEFAULT_REGION=eu-west-1
kubectl apply -f k8s/jobs/dynamodb-job.yaml
kubectl logs -f job/feast-benchmark-dynamodb -n feast-benchmark
```

### 3. Collect Results

```bash
# Apply results collector job
kubectl apply -f k8s/jobs/collect-results.yaml

# Or manually copy results
kubectl cp feast-benchmark/$(kubectl get pods -n feast-benchmark -l app=feast-benchmark -o jsonpath='{.items[0].metadata.name}'):/results ./results
```

### 4. Cleanup

```bash
# Delete all jobs
kubectl delete jobs --all -n feast-benchmark

# Delete everything
kubectl delete -k k8s/overlays/statefarm
```

## Automation Script

```bash
#!/bin/bash
# run_statefarm_benchmark.sh - Run State Farm SLA validation

set -e
NAMESPACE="feast-benchmark"

echo "============================================"
echo "State Farm SLA Benchmark"
echo "Entities: 50, 200 | Features: 200 | SLA: 60ms"
echo "============================================"

# Deploy
echo "Deploying infrastructure..."
kubectl apply -k k8s/overlays/statefarm
kubectl wait --for=condition=available deployment/redis -n $NAMESPACE --timeout=120s
kubectl wait --for=condition=available deployment/postgres -n $NAMESPACE --timeout=120s

# Run benchmarks in parallel
echo "Starting benchmarks..."
kubectl apply -f k8s/jobs/redis-job.yaml
kubectl apply -f k8s/jobs/postgres-job.yaml

# Wait for completion
echo "Waiting for completion..."
kubectl wait --for=condition=complete job/feast-benchmark-redis -n $NAMESPACE --timeout=600s
kubectl wait --for=condition=complete job/feast-benchmark-postgres -n $NAMESPACE --timeout=600s

# Collect results
echo "Collecting results..."
kubectl apply -f k8s/jobs/collect-results.yaml
kubectl wait --for=condition=complete job/feast-benchmark-collect -n $NAMESPACE --timeout=120s

# Copy results locally
mkdir -p results/statefarm
kubectl cp $NAMESPACE/$(kubectl get pods -n $NAMESPACE -l job-name=feast-benchmark-collect -o jsonpath='{.items[0].metadata.name}'):/results ./results/statefarm/

echo "============================================"
echo "Results saved to ./results/statefarm/"
echo "============================================"
ls -la results/statefarm/
```

## Testing Manifests (Dry Run)

```bash
# Validate all overlays
for overlay in base overlays/quick overlays/full overlays/production overlays/statefarm; do
  echo "Testing $overlay..."
  kubectl apply -k k8s/$overlay --dry-run=client
done

# Validate jobs
kubectl apply -f k8s/jobs/redis-job.yaml --dry-run=client
kubectl apply -f k8s/jobs/postgres-job.yaml --dry-run=client
kubectl apply -f k8s/jobs/dynamodb-job.yaml --dry-run=client
```

## OpenShift Notes

```bash
# Use oc instead of kubectl
oc apply -k k8s/overlays/statefarm

# Grant permissions if needed
oc adm policy add-scc-to-user anyuid -z default -n feast-benchmark
```

## ConfigMap Parameters

The benchmark behavior is controlled by the ConfigMap:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `FEATURES` | Feature counts to test | `10,50,100,200` |
| `ENTITIES` | Entity counts to test | `1,10,50,100,200,500` |
| `FV_COUNTS` | Feature View counts | `1,10,50,100` |
| `FEATURE_SERVICES` | Feature Service counts | `1,5,10` |
| `TRANSFORMATIONS` | Transformation modes | `none,python,pandas` |
| `COMPRESSION` | HTTP compression | `none` |
| `ITERATIONS` | Test iterations | `20` |
| `WARMUP` | Warmup iterations | `5` |
| `SLA_P99_MS` | p99 latency target | `60` |
| `SLA_THROUGHPUT_RPH` | Throughput target | `3000000` |

Override via overlay or patch:

```yaml
# kustomization.yaml
configMapGenerator:
  - name: benchmark-config
    behavior: merge
    literals:
      - ENTITIES=50,200
      - FEATURES=200
      - ITERATIONS=50
```
