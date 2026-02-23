#!/bin/bash
# run_statefarm_benchmark.sh - Run State Farm SLA validation benchmarks
#
# Usage:
#   ./run_statefarm_benchmark.sh                    # All stores
#   ./run_statefarm_benchmark.sh redis              # Redis only
#   ./run_statefarm_benchmark.sh redis postgres     # Redis and Postgres
#   ./run_statefarm_benchmark.sh --dry-run          # Validate only

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="feast-benchmark"
TIMEOUT="600s"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
DRY_RUN=false
STORES=()

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        redis|postgres|dynamodb|sqlite)
            STORES+=("$arg")
            ;;
        *)
            log_error "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# Default to all stores if none specified
if [ ${#STORES[@]} -eq 0 ]; then
    STORES=("redis" "postgres")
fi

echo "============================================"
echo "State Farm SLA Benchmark"
echo "============================================"
echo "Entities: 50, 200"
echo "Features: 200"
echo "SLA Target: 60ms p99"
echo "Stores: ${STORES[*]}"
echo "============================================"

cd "$SCRIPT_DIR"

# Dry run mode
if [ "$DRY_RUN" = true ]; then
    log_info "DRY RUN MODE - Validating manifests only"
    echo ""
    
    log_info "Testing overlays..."
    for overlay in base overlays/quick overlays/full overlays/production overlays/statefarm; do
        if kubectl apply -k "$overlay" --dry-run=client > /dev/null 2>&1; then
            echo "  ✓ $overlay"
        else
            echo "  ✗ $overlay"
            exit 1
        fi
    done
    
    log_info "Testing jobs..."
    for store in redis postgres dynamodb sqlite; do
        if kubectl apply -f "jobs/${store}-job.yaml" --dry-run=client > /dev/null 2>&1; then
            echo "  ✓ jobs/${store}-job.yaml"
        else
            echo "  ✗ jobs/${store}-job.yaml"
        fi
    done
    
    echo ""
    log_info "All manifests valid!"
    exit 0
fi

# Deploy infrastructure
log_info "Deploying State Farm overlay..."
kubectl apply -k overlays/statefarm

# Wait for stores
for store in "${STORES[@]}"; do
    if [[ "$store" == "redis" || "$store" == "postgres" ]]; then
        log_info "Waiting for $store deployment..."
        kubectl wait --for=condition=available "deployment/$store" -n "$NAMESPACE" --timeout=120s
    fi
done

# Run benchmarks
log_info "Starting benchmarks..."
for store in "${STORES[@]}"; do
    log_info "Running $store benchmark..."
    
    # Delete existing job if present
    kubectl delete job "feast-benchmark-$store" -n "$NAMESPACE" --ignore-not-found=true
    
    # Apply job
    kubectl apply -f "jobs/${store}-job.yaml"
done

# Wait for completion
log_info "Waiting for benchmarks to complete (timeout: $TIMEOUT)..."
for store in "${STORES[@]}"; do
    log_info "Waiting for $store..."
    if kubectl wait --for=condition=complete "job/feast-benchmark-$store" -n "$NAMESPACE" --timeout="$TIMEOUT"; then
        log_info "$store benchmark completed!"
    else
        log_error "$store benchmark failed or timed out"
        kubectl logs "job/feast-benchmark-$store" -n "$NAMESPACE" --tail=50
    fi
done

# Collect results
log_info "Collecting results..."
mkdir -p ../results/statefarm

for store in "${STORES[@]}"; do
    POD=$(kubectl get pods -n "$NAMESPACE" -l "job-name=feast-benchmark-$store" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [ -n "$POD" ]; then
        log_info "Copying results from $store..."
        kubectl cp "$NAMESPACE/$POD:/results" "../results/statefarm/$store/" 2>/dev/null || true
    fi
done

echo ""
echo "============================================"
echo "BENCHMARK COMPLETE"
echo "============================================"
echo "Results saved to: results/statefarm/"
ls -la ../results/statefarm/ 2>/dev/null || echo "No results found"
echo "============================================"

# Show summary
for store in "${STORES[@]}"; do
    RESULT_FILE="../results/statefarm/$store/benchmark_results.json"
    if [ -f "$RESULT_FILE" ]; then
        log_info "$store results:"
        cat "$RESULT_FILE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('latency', []):
    status = 'PASS' if r['sla_pass'] else 'FAIL'
    print(f\"  {r['num_entities']}e: p50={r['p50']:.1f}ms p99={r['p99']:.1f}ms [{status}]\")
" 2>/dev/null || cat "$RESULT_FILE"
    fi
done
