#!/bin/bash
#
# Run All Feast Benchmarks
#
# Usage:
#   ./run_all_benchmarks.sh              # All stores locally
#   ./run_all_benchmarks.sh --sqlite     # SQLite only
#   ./run_all_benchmarks.sh --redis      # Redis only (requires Docker)
#   ./run_all_benchmarks.sh --dynamodb   # DynamoDB only (requires AWS creds)
#   ./run_all_benchmarks.sh --k8s        # Run in Kubernetes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
RUN_SQLITE=false
RUN_REDIS=false
RUN_DYNAMODB=false
RUN_K8S=false
PRESET="full"

for arg in "$@"; do
    case $arg in
        --sqlite) RUN_SQLITE=true ;;
        --redis) RUN_REDIS=true ;;
        --dynamodb) RUN_DYNAMODB=true ;;
        --k8s) RUN_K8S=true ;;
        --quick) PRESET="quick" ;;
        --full) PRESET="full" ;;
        *) log_warn "Unknown argument: $arg" ;;
    esac
done

# If no specific store selected, run all locally
if ! $RUN_SQLITE && ! $RUN_REDIS && ! $RUN_DYNAMODB && ! $RUN_K8S; then
    RUN_SQLITE=true
    RUN_REDIS=true
fi

# Setup Python environment
setup_venv() {
    if [ ! -d "venv" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
}

# Run SQLite benchmark
run_sqlite() {
    log_info "Running SQLite benchmark..."
    python unified_benchmark.py --preset $PRESET --store sqlite --output results_sqlite
}

# Run Redis benchmark (starts Docker container)
run_redis() {
    log_info "Running Redis benchmark..."
    
    # Start Redis if not running
    if ! docker ps | grep -q redis-feast; then
        log_info "Starting Redis container..."
        docker run -d --name redis-feast -p 6379:6379 redis:7-alpine
        sleep 3
    fi
    
    python unified_benchmark.py --preset $PRESET --store redis --redis-host localhost:6379 --output results_redis
    
    # Cleanup
    log_info "Stopping Redis container..."
    docker stop redis-feast && docker rm redis-feast || true
}

# Run DynamoDB benchmark
run_dynamodb() {
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        log_error "AWS credentials not set. Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        return 1
    fi
    
    REGION="${AWS_DEFAULT_REGION:-us-east-1}"
    log_info "Running DynamoDB benchmark (region: $REGION)..."
    
    python unified_benchmark.py --preset $PRESET --store dynamodb --dynamodb-region $REGION --output results_dynamodb
}

# Run benchmarks in Kubernetes
run_k8s() {
    log_info "Running benchmarks in Kubernetes..."
    
    cd manifests
    
    # Setup
    kubectl apply -f 00-namespace.yaml
    kubectl apply -f 01-redis.yaml
    kubectl wait --for=condition=available deployment/redis -n feast-benchmark --timeout=120s
    
    # Run SQLite job
    log_info "Running SQLite job..."
    kubectl delete job feast-benchmark-sqlite -n feast-benchmark --ignore-not-found
    kubectl apply -f 10-benchmark-job-sqlite.yaml
    kubectl wait --for=condition=complete job/feast-benchmark-sqlite -n feast-benchmark --timeout=600s
    
    # Run Redis job
    log_info "Running Redis job..."
    kubectl delete job feast-benchmark-redis -n feast-benchmark --ignore-not-found
    kubectl apply -f 11-benchmark-job-redis.yaml
    kubectl wait --for=condition=complete job/feast-benchmark-redis -n feast-benchmark --timeout=600s
    
    # Export results
    log_info "Exporting results..."
    mkdir -p ../results_k8s
    
    for store in sqlite redis; do
        POD=$(kubectl get pods -n feast-benchmark -l store=$store -o jsonpath='{.items[0].metadata.name}')
        kubectl cp feast-benchmark/$POD:/results/benchmark_${store}.json ../results_k8s/ || true
    done
    
    cd ..
    log_info "K8s results saved to results_k8s/"
}

# Compare results
compare_results() {
    log_info "Generating comparison report..."
    
    DIRS=""
    NAMES=""
    
    [ -d "results_sqlite" ] && DIRS="$DIRS results_sqlite" && NAMES="$NAMES sqlite"
    [ -d "results_redis" ] && DIRS="$DIRS results_redis" && NAMES="$NAMES redis"
    [ -d "results_dynamodb" ] && DIRS="$DIRS results_dynamodb" && NAMES="$NAMES dynamodb"
    
    if [ -n "$DIRS" ]; then
        python compare_stores.py --dirs $DIRS --names $NAMES --output comparison
        log_info "Comparison report: comparison/comparison_report.md"
    fi
}

# Main
main() {
    echo "=============================================="
    echo "        FEAST BENCHMARK SUITE"
    echo "=============================================="
    echo "Preset: $PRESET"
    echo ""
    
    if $RUN_K8S; then
        run_k8s
    else
        setup_venv
        
        $RUN_SQLITE && run_sqlite
        $RUN_REDIS && run_redis
        $RUN_DYNAMODB && run_dynamodb
        
        compare_results
    fi
    
    echo ""
    echo "=============================================="
    echo "        BENCHMARK COMPLETE"
    echo "=============================================="
    echo ""
    echo "Results directories:"
    ls -d results_* 2>/dev/null || echo "  (none)"
    echo ""
    echo "View reports:"
    echo "  cat results_sqlite/benchmark_report.md"
    echo "  cat comparison/comparison_report.md"
}

main
