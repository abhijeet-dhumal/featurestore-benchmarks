# Kubernetes Deployment

Kustomize-based deployment for Feast benchmark infrastructure.

## Structure

```
k8s/
├── base/                     # Base resources
│   ├── namespace.yaml        # feast-benchmark namespace
│   ├── configmap.yaml        # Benchmark configuration
│   ├── results-pvc.yaml      # Persistent volume for results
│   └── kustomization.yaml
├── jobs/                     # Benchmark job definitions
│   ├── sqlite-job.yaml
│   ├── redis-job.yaml
│   ├── postgres-job.yaml
│   ├── dynamodb-job.yaml
│   ├── profile-job.yaml      # Deep profiling job
│   └── kustomization.yaml
├── stores/                   # Online store deployments
│   ├── redis.yaml
│   ├── postgres.yaml
│   └── kustomization.yaml
└── overlays/                 # Environment-specific configs
    ├── quick/                # Fast testing (fewer iterations)
    ├── statefarm/            # State Farm SLA validation
    ├── production/           # Production-like settings
    └── full/                 # Full test matrix
```

## Quick Start

```bash
# Deploy infrastructure
oc apply -k base
oc apply -k stores

# Wait for pods
oc wait --for=condition=ready pod -l app=redis -n feast-benchmark --timeout=120s
oc wait --for=condition=ready pod -l app=postgres -n feast-benchmark --timeout=120s

# Run benchmark (use parent script instead)
cd .. && ./run_full_benchmark.sh
```

## Manual Job Execution

```bash
# Run individual store benchmark
oc create -f jobs/redis-job.yaml -n feast-benchmark

# Wait for completion
oc wait --for=condition=complete job/feast-benchmark-redis -n feast-benchmark --timeout=900s

# Check logs
oc logs -n feast-benchmark -l store=redis --tail=100
```

## Configuration

### Base ConfigMap (k8s/base/configmap.yaml)

| Parameter | Default | Description |
|-----------|---------|-------------|
| FEATURES | 200 | Number of features |
| ENTITIES | 1,10,50,100,200,500 | Entity counts |
| ITERATIONS | 100 | Test iterations |
| WARMUP | 10 | Warmup iterations |
| SLA_MS | 60 | SLA target (ms) |

### Overlays

| Overlay | Use Case | Entities | Iterations |
|---------|----------|----------|------------|
| quick | Fast testing | 1,10,100 | 20 |
| statefarm | SLA validation | 1,10,50,100,200,500 | 100 |
| production | Production test | 1,10,50,100,200,500 | 100 |
| full | Complete matrix | 1,10,50,100,200,500,1000 | 100 |

```bash
# Use overlay
oc apply -k overlays/statefarm
```

## AWS Credentials (DynamoDB)

```bash
oc create secret generic aws-credentials \
    -n feast-benchmark \
    --from-literal=AWS_ACCESS_KEY_ID=<key> \
    --from-literal=AWS_SECRET_ACCESS_KEY=<secret> \
    --from-literal=AWS_DEFAULT_REGION=eu-west-1
```

## Results

Results are stored in the `benchmark-results` PVC at `/results/<store>/benchmark_results.json`.

```bash
# Access results
oc run results-reader -n feast-benchmark --image=busybox --restart=Never \
    --overrides='{"spec":{"containers":[{"name":"results-reader","image":"busybox","command":["sleep","300"],"volumeMounts":[{"name":"results","mountPath":"/results"}]}],"volumes":[{"name":"results","persistentVolumeClaim":{"claimName":"benchmark-results"}}]}}'

oc exec results-reader -n feast-benchmark -- cat /results/redis/benchmark_results.json
oc delete pod results-reader -n feast-benchmark
```

## Cleanup

```bash
# Delete jobs
oc delete jobs -n feast-benchmark -l app=feast-benchmark

# Delete everything
oc delete namespace feast-benchmark
```
