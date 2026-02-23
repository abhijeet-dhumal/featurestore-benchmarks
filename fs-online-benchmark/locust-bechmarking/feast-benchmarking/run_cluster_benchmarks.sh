#!/bin/bash
# Run all benchmarks in-cluster and collect results
# Usage: ./run_cluster_benchmarks.sh [--stores sqlite,redis,postgres,dynamodb]

set -e

NAMESPACE="feast-test"
STORES="sqlite,redis,postgres"  # Default stores (dynamodb requires AWS secret)
RESULTS_DIR="results"
TIMEOUT="600s"  # 10 minutes per job

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --stores)
            STORES="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "FEAST IN-CLUSTER BENCHMARK RUNNER"
echo "============================================================"
echo "Namespace:  $NAMESPACE"
echo "Stores:     $STORES"
echo "Timeout:    $TIMEOUT"
echo "Results:    $RESULTS_DIR/"
echo "============================================================"

# Ensure namespace exists
kubectl get namespace $NAMESPACE > /dev/null 2>&1 || {
    echo "Error: Namespace $NAMESPACE does not exist"
    exit 1
}

# Create results directories
mkdir -p $RESULTS_DIR/{sqlite,redis,postgres,dynamodb,comparison}

# Function to run benchmark for a store
run_benchmark() {
    local store=$1
    local job_name="feast-benchmark-$store"
    local job_file="k8s/jobs/$store.yaml"
    
    echo ""
    echo "------------------------------------------------------------"
    echo "Running: $store"
    echo "------------------------------------------------------------"
    
    # Check if job manifest exists
    if [[ ! -f "$job_file" ]]; then
        echo "Warning: $job_file not found, skipping $store"
        return
    fi
    
    # Delete previous job if exists
    kubectl delete job $job_name -n $NAMESPACE --ignore-not-found=true 2>/dev/null
    sleep 2
    
    # Apply job
    echo "Applying job: $job_file"
    kubectl apply -f $job_file
    
    # Wait for job to complete
    echo "Waiting for job to complete (timeout: $TIMEOUT)..."
    if kubectl wait --for=condition=complete job/$job_name -n $NAMESPACE --timeout=$TIMEOUT 2>/dev/null; then
        echo "Job completed successfully"
        
        # Get results from logs
        echo "Extracting results..."
        kubectl logs job/$job_name -n $NAMESPACE > /tmp/${store}_full_log.txt 2>&1
        
        # Extract JSON results
        if grep -q '"store":' /tmp/${store}_full_log.txt; then
            # Find the JSON block and save it
            sed -n '/^{$/,/^}$/p' /tmp/${store}_full_log.txt | tail -n +1 > $RESULTS_DIR/$store/benchmark_results.json
            echo "Results saved to: $RESULTS_DIR/$store/benchmark_results.json"
        else
            echo "Warning: Could not extract JSON results from logs"
            cp /tmp/${store}_full_log.txt $RESULTS_DIR/$store/job_output.log
        fi
    else
        echo "Job failed or timed out"
        kubectl logs job/$job_name -n $NAMESPACE --tail=50 || true
        return 1
    fi
}

# Check prerequisites
echo ""
echo "Checking prerequisites..."

# Check if stores are deployed
IFS=',' read -ra STORE_ARRAY <<< "$STORES"
for store in "${STORE_ARRAY[@]}"; do
    case $store in
        redis)
            kubectl get svc redis -n $NAMESPACE > /dev/null 2>&1 || {
                echo "Deploying Redis..."
                kubectl apply -f k8s/01-redis.yaml
                kubectl wait --for=condition=available deployment/redis -n $NAMESPACE --timeout=120s
            }
            ;;
        postgres)
            kubectl get svc postgres -n $NAMESPACE > /dev/null 2>&1 || {
                echo "Deploying PostgreSQL..."
                kubectl apply -f k8s/04-postgres.yaml
                kubectl wait --for=condition=available deployment/postgres -n $NAMESPACE --timeout=120s
            }
            ;;
        dynamodb)
            kubectl get secret aws-secret -n $NAMESPACE > /dev/null 2>&1 || {
                echo "Warning: aws-secret not found. DynamoDB benchmark requires AWS credentials."
                echo "Create secret: kubectl create secret generic aws-secret -n $NAMESPACE \\"
                echo "  --from-literal=AWS_ACCESS_KEY_ID=xxx \\"
                echo "  --from-literal=AWS_SECRET_ACCESS_KEY=xxx \\"
                echo "  --from-literal=AWS_DEFAULT_REGION=us-east-1"
            }
            ;;
        sqlite)
            # No prerequisites for SQLite
            ;;
    esac
done

echo ""
echo "Running benchmarks..."

# Run benchmarks for each store
for store in "${STORE_ARRAY[@]}"; do
    run_benchmark $store || echo "Warning: $store benchmark failed"
done

# Generate comparison charts
echo ""
echo "------------------------------------------------------------"
echo "Generating comparison charts"
echo "------------------------------------------------------------"

# Build chart generation arguments
CHART_DIRS=""
CHART_NAMES=""
for store in "${STORE_ARRAY[@]}"; do
    if [[ -f "$RESULTS_DIR/$store/benchmark_results.json" ]]; then
        CHART_DIRS="$CHART_DIRS $RESULTS_DIR/$store"
        CHART_NAMES="$CHART_NAMES $store"
    fi
done

if [[ -n "$CHART_DIRS" ]]; then
    echo "Generating charts for:$CHART_NAMES"
    python generate_charts.py --dirs $CHART_DIRS --names $CHART_NAMES --output $RESULTS_DIR/comparison
else
    echo "No results to generate charts from"
fi

echo ""
echo "============================================================"
echo "BENCHMARK COMPLETE"
echo "============================================================"
echo ""
echo "Results:"
ls -la $RESULTS_DIR/*/benchmark_results.json 2>/dev/null || echo "  (no results found)"
echo ""
echo "Charts:"
ls -la $RESULTS_DIR/comparison/*.png 2>/dev/null || echo "  (no charts generated)"
echo ""
echo "============================================================"
