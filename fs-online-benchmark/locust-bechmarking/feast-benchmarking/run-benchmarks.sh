#!/bin/bash
#
# Feast Benchmark Automation
# One-command benchmark suite with automatic chart generation
#
# Usage:
#   ./run-benchmarks.sh quick           # Quick test (50 features, 100 entities)
#   ./run-benchmarks.sh production      # Production scale (200 features, 500 entities)
#   ./run-benchmarks.sh full            # Full matrix (200 features, 1000 entities)
#   ./run-benchmarks.sh --cleanup       # Remove all resources
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/k8s"
RESULTS_DIR="${SCRIPT_DIR}/results"
NAMESPACE="feast-benchmark"
OVERLAY="${1:-production}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
header() { echo -e "\n${CYAN}═══════════════════════════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}\n"; }

usage() {
    cat <<EOF
Feast Benchmark Automation Suite

Usage: $0 [OVERLAY] [OPTIONS]

OVERLAYS:
  quick       50 features, 1/10/100 entities, 10 iterations (~3 min)
  production  200 features, 1/10/100/500 entities, 20 iterations (~10 min)
  full        200 features, 1-1000 entities, 50 iterations (~30 min)

OPTIONS:
  --cleanup           Remove all benchmark resources
  --skip-dynamodb     Skip DynamoDB benchmark (no AWS creds needed)
  --charts-only       Only generate charts from existing results
  --help              Show this help

PREREQUISITES:
  - kubectl configured with cluster access
  - nfs-csi StorageClass available
  - For DynamoDB: aws-credentials secret in namespace or feast-test

EXAMPLES:
  $0 production                    # Full production benchmark
  $0 quick --skip-dynamodb         # Quick test without AWS
  $0 --charts-only                 # Regenerate charts only
  $0 --cleanup                     # Clean up everything
EOF
    exit 0
}

# Parse arguments
SKIP_DYNAMODB=false
CHARTS_ONLY=false
CLEANUP=false

for arg in "$@"; do
    case "$arg" in
        --cleanup) CLEANUP=true ;;
        --skip-dynamodb) SKIP_DYNAMODB=true ;;
        --charts-only) CHARTS_ONLY=true ;;
        --help|-h) usage ;;
        quick|production|full) OVERLAY="$arg" ;;
    esac
done

cleanup() {
    header "CLEANUP"
    log "Removing namespace ${NAMESPACE}..."
    kubectl delete namespace "$NAMESPACE" --ignore-not-found=true --wait=false 2>/dev/null || true
    kubectl wait --for=delete namespace/"$NAMESPACE" --timeout=120s 2>/dev/null || true
    success "Cleanup complete"
}

generate_charts() {
    header "CHART GENERATION"
    
    # Setup Python venv if needed
    if [[ ! -d "${SCRIPT_DIR}/venv" ]]; then
        log "Creating Python virtual environment..."
        python3 -m venv "${SCRIPT_DIR}/venv"
        source "${SCRIPT_DIR}/venv/bin/activate"
        pip install -q matplotlib numpy
    else
        source "${SCRIPT_DIR}/venv/bin/activate"
    fi
    
    local RESULT_BASE="${RESULTS_DIR}/${OVERLAY}"
    local OUTPUT_DIR="${RESULTS_DIR}/comparison"
    mkdir -p "$OUTPUT_DIR"
    
    # Find available stores
    local STORES=()
    local STORE_DIRS=()
    for store in sqlite redis postgres dynamodb; do
        if [[ -f "${RESULT_BASE}/${store}/benchmark_results.json" ]]; then
            STORES+=("$store")
            STORE_DIRS+=("${RESULT_BASE}/${store}")
        fi
    done
    
    if [[ ${#STORES[@]} -eq 0 ]]; then
        warn "No benchmark results found in ${RESULT_BASE}/"
        return 1
    fi
    
    log "Generating comparison charts for: ${STORES[*]}"
    
    # Generate comparison charts (01-04)
    python3 "${SCRIPT_DIR}/generate_charts.py" \
        --dirs ${STORE_DIRS[@]} \
        --names ${STORES[@]} \
        --output "$OUTPUT_DIR"
    
    # Generate profile charts (05-08) if profile results exist
    if [[ -f "${RESULT_BASE}/profile/deep_profile_results.json" ]]; then
        log "Generating profile charts..."
        python3 "${SCRIPT_DIR}/generate_profile_charts.py" \
            --input "${RESULT_BASE}/profile/deep_profile_results.json" \
            --output "$OUTPUT_DIR"
    fi
    
    success "Charts saved to ${OUTPUT_DIR}/"
    ls -la "$OUTPUT_DIR"/*.png 2>/dev/null | awk '{print "  " $NF}'
}

copy_results() {
    header "COPYING RESULTS"
    
    local RESULT_BASE="${RESULTS_DIR}/${OVERLAY}"
    mkdir -p "$RESULT_BASE"
    
    log "Creating results copier pod..."
    kubectl run results-copier \
        --image=busybox \
        --restart=Never \
        --overrides="{\"spec\":{\"containers\":[{\"name\":\"copier\",\"image\":\"busybox\",\"command\":[\"sleep\",\"120\"],\"volumeMounts\":[{\"name\":\"r\",\"mountPath\":\"/results\"}]}],\"volumes\":[{\"name\":\"r\",\"persistentVolumeClaim\":{\"claimName\":\"benchmark-results\"}}]}}" \
        -n "$NAMESPACE" 2>/dev/null || true
    
    kubectl wait --for=condition=Ready pod/results-copier -n "$NAMESPACE" --timeout=60s
    
    log "Copying results from PVC..."
    for store in sqlite redis postgres dynamodb profile; do
        kubectl cp "${NAMESPACE}/results-copier:/results/${store}" "${RESULT_BASE}/${store}" 2>/dev/null && \
            success "Copied: ${store}" || true
    done
    
    kubectl delete pod results-copier -n "$NAMESPACE" --wait=false 2>/dev/null || true
    
    success "Results saved to ${RESULT_BASE}/"
}

wait_for_jobs() {
    local JOBS=("$@")
    local FAILED=()
    
    for job in "${JOBS[@]}"; do
        log "Waiting for ${job}..."
        if kubectl wait --for=condition=complete "job/${job}" -n "$NAMESPACE" --timeout=900s 2>/dev/null; then
            success "${job} completed"
        else
            warn "${job} may have failed"
            FAILED+=("$job")
        fi
    done
    
    if [[ ${#FAILED[@]} -gt 0 ]]; then
        warn "Failed jobs: ${FAILED[*]}"
        for job in "${FAILED[@]}"; do
            echo "--- Logs for ${job} ---"
            kubectl logs "job/${job}" -n "$NAMESPACE" --tail=20 2>/dev/null || true
        done
    fi
}

# Main execution
if [[ "$CLEANUP" == "true" ]]; then
    cleanup
    exit 0
fi

if [[ "$CHARTS_ONLY" == "true" ]]; then
    generate_charts
    exit 0
fi

# Verify prerequisites
if ! command -v kubectl &>/dev/null; then
    error "kubectl not found"
    exit 1
fi

if [[ ! -d "${K8S_DIR}/overlays/${OVERLAY}" ]]; then
    error "Unknown overlay: ${OVERLAY}"
    echo "Available: quick, production, full"
    exit 1
fi

header "FEAST BENCHMARK SUITE"
echo "  Overlay:    ${OVERLAY}"
echo "  Namespace:  ${NAMESPACE}"
echo "  Results:    ${RESULTS_DIR}/${OVERLAY}/"
echo ""

# Step 1: Clean up existing resources
log "Cleaning up existing namespace..."
kubectl delete namespace "$NAMESPACE" --ignore-not-found=true --wait=false 2>/dev/null || true
kubectl wait --for=delete namespace/"$NAMESPACE" --timeout=60s 2>/dev/null || true

# Step 2: Deploy everything with kustomize
header "DEPLOYING INFRASTRUCTURE"
log "Applying kustomize overlay: ${OVERLAY}"
kubectl apply -k "${K8S_DIR}/overlays/${OVERLAY}"
success "Resources created"

# Step 3: Wait for stores to be ready
log "Waiting for online stores..."
sleep 5
kubectl wait --for=condition=Available deployment/redis -n "$NAMESPACE" --timeout=120s
kubectl wait --for=condition=Available deployment/postgres -n "$NAMESPACE" --timeout=120s
success "Stores ready"

# Step 4: Copy AWS credentials if available
if kubectl get secret aws-credentials -n feast-test 2>/dev/null && [[ "$SKIP_DYNAMODB" != "true" ]]; then
    log "Copying AWS credentials from feast-test..."
    kubectl get secret aws-credentials -n feast-test -o yaml | \
        sed "s/namespace: feast-test/namespace: ${NAMESPACE}/" | \
        kubectl apply -f - 2>/dev/null || true
    success "AWS credentials available"
else
    if [[ "$SKIP_DYNAMODB" != "true" ]]; then
        warn "No AWS credentials found - DynamoDB will be skipped"
    fi
    SKIP_DYNAMODB=true
fi

# Step 5: Wait for benchmark jobs
header "RUNNING BENCHMARKS"

# Delete auto-started jobs and restart them (they may have started before stores were ready)
log "Restarting benchmark jobs..."
kubectl delete jobs -l app=feast-benchmark -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
sleep 2

# Apply jobs individually
kubectl apply -f "${K8S_DIR}/jobs/sqlite-job.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/jobs/redis-job.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/jobs/postgres-job.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/jobs/profile-job.yaml" -n "$NAMESPACE"

JOBS=("feast-benchmark-sqlite" "feast-benchmark-redis" "feast-benchmark-postgres" "feast-benchmark-profile")

if [[ "$SKIP_DYNAMODB" != "true" ]]; then
    kubectl apply -f "${K8S_DIR}/jobs/dynamodb-job.yaml" -n "$NAMESPACE"
    JOBS+=("feast-benchmark-dynamodb")
fi

log "Jobs submitted: ${JOBS[*]}"
echo ""

wait_for_jobs "${JOBS[@]}"

# Step 6: Show results summary
header "RESULTS SUMMARY"
for job in "${JOBS[@]}"; do
    echo -e "\n${CYAN}--- ${job} ---${NC}"
    kubectl logs "job/${job}" -n "$NAMESPACE" --tail=10 2>/dev/null | grep -E "^\d+e:|^======|p50=|p99=|Saved:" || true
done

# Step 7: Copy results locally
copy_results

# Step 8: Generate charts
generate_charts

# Final summary
header "BENCHMARK COMPLETE"
echo "Results:  ${RESULTS_DIR}/${OVERLAY}/"
echo "Charts:   ${RESULTS_DIR}/comparison/"
echo ""
echo "View charts:"
echo "  open ${RESULTS_DIR}/comparison/"
echo ""
echo "Cleanup:"
echo "  $0 --cleanup"
echo ""
success "Done!"
