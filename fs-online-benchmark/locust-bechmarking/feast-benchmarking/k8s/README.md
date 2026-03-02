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
├── build/                    # Custom image build resources
│   ├── imagestream.yaml      # ImageStream for feast-benchmark
│   └── buildconfig.yaml      # BuildConfig for Docker builds
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

## Building Custom Feast Image

The benchmark jobs use a pre-built image with all feast dependencies. This is required when testing custom feast branches (e.g., from a git reference).

### Why Build a Custom Image?

- OpenShift containers run as non-root, so `apt-get install git` fails at runtime
- Installing feast from git at runtime is slow and unreliable
- Pre-built image includes all dependencies for fast job startup

### Step 1: Create ImageStream and BuildConfig

```bash
# Create the ImageStream (stores built images)
oc apply -f k8s/build/imagestream.yaml

# Create the BuildConfig (defines how to build)
oc apply -f k8s/build/buildconfig.yaml
```

### Step 2: Configure Dockerfile for Custom Feast Branch

Edit the `Dockerfile` to install feast from your desired git reference:

```dockerfile
# Install feast from custom git branch
RUN pip install --no-cache-dir --no-deps \
    "feast[redis,aws,postgres] @ git+https://github.com/YOUR_USER/feast.git@YOUR_BRANCH#subdirectory=sdk/python"
```

The Dockerfile pre-installs all feast dependencies first, then installs feast with `--no-deps` to avoid version conflicts.

### Step 3: Build the Image

```bash
# Start the build from local directory
oc start-build feast-benchmark -n feast-benchmark \
    --from-dir=. \
    --follow

# Or without --follow to run in background
oc start-build feast-benchmark -n feast-benchmark --from-dir=.

# Monitor build progress
oc get builds -n feast-benchmark
oc logs -f build/feast-benchmark-1 -n feast-benchmark
```

Build typically takes 5-10 minutes (cloning git repo + installing dependencies).

### Step 4: Verify the Image

```bash
# Check ImageStream has the new image
oc get imagestream feast-benchmark -n feast-benchmark

# Get the full image URL
oc get imagestream feast-benchmark -n feast-benchmark \
    -o jsonpath='{.status.dockerImageRepository}'
# Output: image-registry.openshift-image-registry.svc:5000/feast-benchmark/feast-benchmark
```

### Step 5: Update Job Definitions

The job YAML files should reference the built image:

```yaml
containers:
  - name: benchmark
    image: image-registry.openshift-image-registry.svc:5000/feast-benchmark/feast-benchmark:latest
```

### Rebuilding After Changes

```bash
# Clean up old builds (optional)
oc delete builds -n feast-benchmark --all

# Start new build
oc start-build feast-benchmark -n feast-benchmark --from-dir=. --follow
```

## Quick Start

### Prerequisites

```bash
# 1. Deploy infrastructure
oc apply -k base
oc apply -k stores

# 2. Wait for pods
oc wait --for=condition=ready pod -l app=redis -n feast-benchmark --timeout=120s
oc wait --for=condition=ready pod -l app=postgres -n feast-benchmark --timeout=120s

# 3. Create AWS credentials (for DynamoDB tests)
oc create secret generic aws-credentials -n feast-benchmark \
    --from-literal=AWS_ACCESS_KEY_ID=<key> \
    --from-literal=AWS_SECRET_ACCESS_KEY=<secret> \
    --from-literal=AWS_DEFAULT_REGION=eu-west-1

# 4. Build custom feast image (if using git reference)
oc apply -f k8s/build/imagestream.yaml
oc apply -f k8s/build/buildconfig.yaml
oc start-build feast-benchmark -n feast-benchmark --from-dir=. --follow
```

### Run Full Benchmark Automation

```bash
# Run with defaults from benchmark.config.yaml
./run_full_benchmark.sh

# Run with custom feast branch (triggers image rebuild)
./run_full_benchmark.sh --feast-git-ref perf/my-optimization

# Run with custom feast repo and branch
./run_full_benchmark.sh \
    --feast-git-url https://github.com/myuser/feast.git \
    --feast-git-ref my-feature-branch

# Use different config file
./run_full_benchmark.sh --config production.config.yaml

# Run specific stores only
./run_full_benchmark.sh --stores "redis postgres"

# Skip image rebuild (use existing image)
./run_full_benchmark.sh --feast-git-ref my-branch --skip-build

# Custom configuration
./run_full_benchmark.sh --entities "1 10 50 100" --iterations 200

# Dry run to see commands
./run_full_benchmark.sh --dry-run --verbose
```

The automation script will:
1. Load configuration from `benchmark.config.yaml`
2. Build custom feast image (if `--feast-git-ref` specified)
3. Create benchmark jobs for each store
4. Wait for all jobs to complete
5. Collect results from the PVC
6. Generate comparison charts

### Results Location

After completion, results are saved to:
- `results/<store>/benchmark_results.json` - Raw benchmark data
- `results/charts/` - Generated comparison charts

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

### Config File (benchmark.config.yaml)

All benchmark settings are centralized in `benchmark.config.yaml`. Edit this file instead of modifying scripts.

```yaml
# Feast source - git reference or PyPI
feast:
  source: git
  git_url: "https://github.com/abhijeet-dhumal/feast.git"
  git_ref: "perf/combined-optimizations"
  extras: "redis,aws,postgres"

# Benchmark parameters
benchmark:
  features: 200
  entities: [1, 10, 50, 100, 200, 500]
  iterations: 300
  warmup: 20
  sla_ms: 60

# Store-specific settings
stores:
  redis:
    enabled: true
    iterations: 300
    warmup: 20
    connection:
      host: "redis.feast-benchmark.svc.cluster.local"
      port: 6379
  postgres:
    enabled: true
    iterations: 300
    warmup: 25
    connection:
      host: "postgres.feast-benchmark.svc.cluster.local"
      port: 5432
      database: "feast"
      user: "feast"
      password: "feast"
  dynamodb:
    enabled: true
    iterations: 500
    warmup: 30
    connection:
      region: "eu-west-1"
```

Command-line arguments override config file settings.

### Base ConfigMap (k8s/base/configmap.yaml)

| Parameter | Default | Description |
|-----------|---------|-------------|
| FEATURES | 200 | Number of features |
| ENTITIES | 1,10,50,100,200,500 | Entity counts |
| ITERATIONS | 300 | Test iterations (store-specific in jobs) |
| WARMUP | 20 | Warmup iterations (store-specific in jobs) |
| SLA_MS | 60 | SLA target (ms) |

### Store-Specific Defaults (for reliability)

| Store | Iterations | Warmup | Rationale |
|-------|------------|--------|-----------|
| SQLite | 200 | 10 | Lower variance, local store |
| Redis | 300 | 20 | Network variance, connection pooling warmup |
| PostgreSQL | 300 | 25 | Connection pool + query cache warmup |
| DynamoDB | 500 | 30 | Higher variance due to AWS API latency |

### Overlays

| Overlay | Use Case | Entities | Iterations |
|---------|----------|----------|------------|
| quick | Fast testing | 1,10,100 | 50 |
| statefarm | SLA validation | 1,10,50,100,200,500 | 300 |
| production | Production test | 1,10,50,100,200,500 | 300 |
| full | Complete matrix | 1,10,50,100,200,500,1000 | 500 |

```bash
# Use overlay
oc apply -k overlays/statefarm
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

## Reliability Metrics

Results now include Coefficient of Variation (CV) to assess measurement reliability:

| CV | Status | Action |
|----|--------|--------|
| < 15% | ✓ Good | Results reliable |
| 15-25% | ⚠ Warning | Consider re-running with more iterations |
| > 25% | ✗ Poor | Re-run required |

## Cleanup

```bash
# Delete jobs only
oc delete jobs -n feast-benchmark -l app=feast-benchmark

# Delete builds (keep buildconfig/imagestream)
oc delete builds -n feast-benchmark --all

# Delete results-reader pod if stuck
oc delete pod results-reader -n feast-benchmark --ignore-not-found

# Full cleanup (delete everything including namespace)
oc delete namespace feast-benchmark
```

## Complete Workflow Example

Here's the full workflow for running benchmarks with a custom feast branch:

```bash
# 1. Setup namespace and infra
oc apply -k k8s/base
oc apply -k k8s/stores

# 2. Wait for stores to be ready
oc wait --for=condition=ready pod -l app=redis -n feast-benchmark --timeout=120s
oc wait --for=condition=ready pod -l app=postgres -n feast-benchmark --timeout=120s

# 3. Create AWS credentials for DynamoDB
oc create secret generic aws-credentials -n feast-benchmark \
    --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    --from-literal=AWS_DEFAULT_REGION=eu-west-1

# 4. Run benchmarks with custom feast branch (auto-builds image)
./run_full_benchmark.sh \
    --feast-git-ref perf/combined-optimizations \
    --feast-git-url https://github.com/abhijeet-dhumal/feast.git

# Or use config file (edit benchmark.config.yaml first)
./run_full_benchmark.sh

# 5. Check results
ls -la results/

# 6. View charts
open results/charts/*.png

# 7. Cleanup when done
oc delete jobs -n feast-benchmark -l app=feast-benchmark
```

### Quick Re-run (skip rebuild)

If you've already built the image and just want to re-run benchmarks:

```bash
./run_full_benchmark.sh --skip-build
```
