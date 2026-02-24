#!/bin/bash
#===============================================================================
# Feast Online Store Benchmark - Full Cycle Automation
#===============================================================================
#
# DESCRIPTION:
#   Single source of truth for running end-to-end performance evaluation
#   across all online stores (SQLite, Redis, PostgreSQL, DynamoDB).
#
# USAGE:
#   ./run_full_benchmark.sh [OPTIONS]
#
# OPTIONS:
#   --stores <list>       Stores to benchmark (default: "sqlite redis postgres dynamodb")
#   --namespace <ns>      Kubernetes namespace (default: feast-benchmark)
#   --features <n>        Number of features (default: 200)
#   --entities <list>     Entity counts to test (default: "1 10 50 100 200 500")
#   --iterations <n>      Iterations per test (default: 100)
#   --warmup <n>          Warmup iterations (default: 10)
#   --timeout <s>         Job timeout in seconds (default: 900)
#   --output-dir <dir>    Results output directory (default: results/cluster)
#   --skip-k8s            Skip K8s jobs, run locally only (SQLite)
#   --skip-charts         Skip chart generation
#   --dry-run             Show what would be done without executing
#   --verbose             Enable verbose output
#   --help                Show this help message
#
# PREREQUISITES:
#   - oc/kubectl CLI configured with cluster access
#   - Python 3.11+ with venv
#   - Namespace with Redis, Postgres pods running
#   - AWS credentials secret (for DynamoDB)
#
# EXAMPLES:
#   # Run all stores with defaults
#   ./run_full_benchmark.sh
#
#   # Run only Redis and Postgres
#   ./run_full_benchmark.sh --stores "redis postgres"
#
#   # Custom entity counts
#   ./run_full_benchmark.sh --entities "1 50 100 500"
#
#   # Dry run to see commands
#   ./run_full_benchmark.sh --dry-run --verbose
#
#===============================================================================

set -euo pipefail

#-------------------------------------------------------------------------------
# Configuration Defaults
#-------------------------------------------------------------------------------
STORES="sqlite redis postgres dynamodb"
NAMESPACE="feast-benchmark"
FEATURES=200
ENTITIES="1 10 50 100 200 500"
ITERATIONS=100
WARMUP=10
TIMEOUT=900
OUTPUT_DIR="results"
SKIP_K8S=false
SKIP_CHARTS=false
DRY_RUN=false
VERBOSE=false

# Script directory (for relative paths)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS_DIR="${SCRIPT_DIR}/k8s/jobs"
CHARTS_OUTPUT="${SCRIPT_DIR}/results/charts"

# Kubernetes CLI (oc or kubectl)
K8S_CLI="oc"
if ! command -v oc &>/dev/null; then
    K8S_CLI="kubectl"
fi

#-------------------------------------------------------------------------------
# Colors and Logging
#-------------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_verbose() { [[ "$VERBOSE" == "true" ]] && echo -e "${CYAN}[DEBUG]${NC} $*" || true; }

log_header() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  $*${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
}

log_section() {
    echo ""
    echo -e "${BLUE}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}  $*${NC}"
    echo -e "${BLUE}───────────────────────────────────────────────────────────────${NC}"
}

#-------------------------------------------------------------------------------
# Help
#-------------------------------------------------------------------------------
show_help() {
    head -50 "$0" | grep -E "^#" | sed 's/^#//' | sed 's/^!/#!/'
    exit 0
}

#-------------------------------------------------------------------------------
# Argument Parsing
#-------------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --stores)       STORES="$2"; shift 2 ;;
            --namespace)    NAMESPACE="$2"; shift 2 ;;
            --features)     FEATURES="$2"; shift 2 ;;
            --entities)     ENTITIES="$2"; shift 2 ;;
            --iterations)   ITERATIONS="$2"; shift 2 ;;
            --warmup)       WARMUP="$2"; shift 2 ;;
            --timeout)      TIMEOUT="$2"; shift 2 ;;
            --output-dir)   OUTPUT_DIR="$2"; shift 2 ;;
            --skip-k8s)     SKIP_K8S=true; shift ;;
            --skip-charts)  SKIP_CHARTS=true; shift ;;
            --dry-run)      DRY_RUN=true; shift ;;
            --verbose)      VERBOSE=true; shift ;;
            --help|-h)      show_help ;;
            *)              log_error "Unknown option: $1"; exit 1 ;;
        esac
    done
}

#-------------------------------------------------------------------------------
# Utility Functions
#-------------------------------------------------------------------------------
run_cmd() {
    local cmd="$*"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $cmd"
        return 0
    fi
    log_verbose "Executing: $cmd"
    eval "$cmd"
}

check_prerequisites() {
    log_section "Checking Prerequisites"
    
    # Check K8s CLI
    if ! command -v "$K8S_CLI" &>/dev/null; then
        log_error "Neither 'oc' nor 'kubectl' found. Please install one."
        exit 1
    fi
    log_success "K8s CLI: $K8S_CLI"
    
    # Check Python
    if ! command -v python3 &>/dev/null; then
        log_error "python3 not found"
        exit 1
    fi
    log_success "Python: $(python3 --version)"
    
    # Check cluster connection
    if ! $K8S_CLI cluster-info &>/dev/null; then
        log_error "Not connected to Kubernetes cluster"
        exit 1
    fi
    log_success "Cluster: connected"
    
    # Check namespace
    if ! $K8S_CLI get namespace "$NAMESPACE" &>/dev/null; then
        log_error "Namespace '$NAMESPACE' not found"
        exit 1
    fi
    log_success "Namespace: $NAMESPACE"
    
    # Check required pods
    for pod_prefix in redis postgres; do
        if [[ "$STORES" == *"$pod_prefix"* ]] || [[ "$pod_prefix" == "redis" && "$STORES" == *"dynamodb"* ]]; then
            if ! $K8S_CLI get pods -n "$NAMESPACE" -l app="$pod_prefix" --no-headers 2>/dev/null | grep -q Running; then
                log_warn "$pod_prefix pod not running (may be optional)"
            else
                log_success "$pod_prefix pod: running"
            fi
        fi
    done
    
    # Check AWS credentials for DynamoDB
    if [[ "$STORES" == *"dynamodb"* ]]; then
        if ! $K8S_CLI get secret aws-credentials -n "$NAMESPACE" &>/dev/null; then
            log_error "AWS credentials secret not found (required for DynamoDB)"
            exit 1
        fi
        log_success "AWS credentials: found"
    fi
}

setup_local_env() {
    log_section "Setting Up Local Environment"
    
    cd "$SCRIPT_DIR"
    
    if [[ ! -d ".venv" ]]; then
        log_info "Creating Python virtual environment..."
        run_cmd "python3 -m venv .venv"
    fi
    
    log_info "Installing dependencies..."
    run_cmd "./.venv/bin/pip install -q feast matplotlib numpy pandas"
    
    log_success "Local environment ready"
}

#-------------------------------------------------------------------------------
# K8s Job Management
#-------------------------------------------------------------------------------
delete_existing_jobs() {
    local store="$1"
    log_verbose "Deleting existing job for $store..."
    run_cmd "$K8S_CLI delete job feast-benchmark-${store} -n $NAMESPACE --ignore-not-found 2>/dev/null || true"
}

create_job() {
    local store="$1"
    local job_file="${JOBS_DIR}/${store}-job.yaml"
    
    if [[ ! -f "$job_file" ]]; then
        log_error "Job file not found: $job_file"
        return 1
    fi
    
    log_info "Creating job for $store..."
    run_cmd "$K8S_CLI create -f $job_file -n $NAMESPACE"
}

wait_for_job() {
    local store="$1"
    log_info "Waiting for $store job to complete (timeout: ${TIMEOUT}s)..."
    run_cmd "$K8S_CLI wait --for=condition=complete job/feast-benchmark-${store} -n $NAMESPACE --timeout=${TIMEOUT}s"
}

get_job_logs() {
    local store="$1"
    log_verbose "Getting logs for $store..."
    $K8S_CLI logs -n "$NAMESPACE" -l store="$store" --tail=50 2>/dev/null || true
}

#-------------------------------------------------------------------------------
# Results Collection
#-------------------------------------------------------------------------------
create_results_reader() {
    log_info "Creating results reader pod..."
    run_cmd "$K8S_CLI delete pod results-reader -n $NAMESPACE --ignore-not-found 2>/dev/null || true"
    sleep 2
    
    run_cmd "$K8S_CLI run results-reader -n $NAMESPACE --image=busybox --restart=Never \
        --overrides='{\"spec\":{\"containers\":[{\"name\":\"results-reader\",\"image\":\"busybox\",\"command\":[\"sleep\",\"3600\"],\"volumeMounts\":[{\"name\":\"results\",\"mountPath\":\"/results\"}]}],\"volumes\":[{\"name\":\"results\",\"persistentVolumeClaim\":{\"claimName\":\"benchmark-results\"}}]}}'"
    
    log_info "Waiting for results reader pod..."
    run_cmd "$K8S_CLI wait --for=condition=ready pod/results-reader -n $NAMESPACE --timeout=60s"
}

fetch_results() {
    local store="$1"
    local output_file="${SCRIPT_DIR}/${OUTPUT_DIR}/${store}/benchmark_results.json"
    
    log_info "Fetching results for $store..."
    mkdir -p "$(dirname "$output_file")"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} Would fetch /results/${store}/benchmark_results.json to $output_file"
        return 0
    fi
    
    $K8S_CLI exec results-reader -n "$NAMESPACE" -- cat "/results/${store}/benchmark_results.json" > "$output_file" 2>/dev/null
    
    if [[ -s "$output_file" ]]; then
        log_success "Saved: $output_file"
    else
        log_warn "No results found for $store"
    fi
}

cleanup_results_reader() {
    log_info "Cleaning up results reader pod..."
    run_cmd "$K8S_CLI delete pod results-reader -n $NAMESPACE --ignore-not-found 2>/dev/null || true"
}

#-------------------------------------------------------------------------------
# Local Benchmark (SQLite)
#-------------------------------------------------------------------------------
run_local_benchmark() {
    local store="$1"
    
    log_info "Running local benchmark for $store..."
    
    local entities_arg=$(echo "$ENTITIES" | tr ' ' ' ')
    local output_path="${SCRIPT_DIR}/${OUTPUT_DIR}/${store}"
    
    run_cmd "./.venv/bin/python unified_benchmark.py \
        --store $store \
        --features $FEATURES \
        --entities $entities_arg \
        --iterations $ITERATIONS \
        --warmup $WARMUP \
        --output $output_path"
}

#-------------------------------------------------------------------------------
# Chart Generation
#-------------------------------------------------------------------------------
generate_charts() {
    log_section "Generating Charts"
    
    local dirs=""
    local names=""
    
    for store in $STORES; do
        local result_dir="${SCRIPT_DIR}/${OUTPUT_DIR}/${store}"
        if [[ -f "${result_dir}/benchmark_results.json" ]]; then
            dirs="$dirs $result_dir"
            names="$names $store"
        else
            log_warn "No results for $store, skipping in charts"
        fi
    done
    
    if [[ -z "$dirs" ]]; then
        log_error "No results found for chart generation"
        return 1
    fi
    
    mkdir -p "$CHARTS_OUTPUT"
    
    run_cmd "./.venv/bin/python generate_charts.py \
        --dirs $dirs \
        --names $names \
        --output $CHARTS_OUTPUT"
    
    log_success "Charts saved to: $CHARTS_OUTPUT"
}

#-------------------------------------------------------------------------------
# Summary Report
#-------------------------------------------------------------------------------
print_summary() {
    log_header "Benchmark Summary"
    
    echo ""
    echo "Configuration:"
    echo "  Features:    $FEATURES"
    echo "  Entities:    $ENTITIES"
    echo "  Iterations:  $ITERATIONS"
    echo "  Warmup:      $WARMUP"
    echo "  Stores:      $STORES"
    echo ""
    
    echo "Results (p99 latency @ 500 entities):"
    echo "┌──────────┬──────────┬────────┐"
    echo "│  Store   │  p99(ms) │  SLA   │"
    echo "├──────────┼──────────┼────────┤"
    
    for store in $STORES; do
        local result_file="${SCRIPT_DIR}/${OUTPUT_DIR}/${store}/benchmark_results.json"
        if [[ -f "$result_file" ]]; then
            local p99=$(python3 -c "
import json
with open('$result_file') as f:
    data = json.load(f)
latency = data.get('latency', [])
for r in latency:
    if r.get('num_entities') == 500:
        print(f\"{r.get('p99', 0):.1f}\")
        break
else:
    print('N/A')
" 2>/dev/null || echo "N/A")
            
            local sla_status="❌ FAIL"
            if [[ "$p99" != "N/A" ]] && (( $(echo "$p99 < 60" | bc -l 2>/dev/null || echo 0) )); then
                sla_status="✅ PASS"
            fi
            
            printf "│ %-8s │ %8s │ %-6s │\n" "$store" "$p99" "$sla_status"
        else
            printf "│ %-8s │ %8s │ %-6s │\n" "$store" "N/A" "N/A"
        fi
    done
    
    echo "└──────────┴──────────┴────────┘"
    echo ""
    echo "Charts:  $CHARTS_OUTPUT"
    echo "Results: ${SCRIPT_DIR}/${OUTPUT_DIR}/"
}

#-------------------------------------------------------------------------------
# Main Execution
#-------------------------------------------------------------------------------
main() {
    parse_args "$@"
    
    log_header "Feast Online Store Benchmark"
    echo ""
    echo "  Stores:     $STORES"
    echo "  Features:   $FEATURES"
    echo "  Entities:   $ENTITIES"
    echo "  Iterations: $ITERATIONS"
    echo "  Warmup:     $WARMUP"
    echo "  Namespace:  $NAMESPACE"
    echo "  Dry Run:    $DRY_RUN"
    echo ""
    
    check_prerequisites
    setup_local_env
    
    # Track which stores to fetch from K8s
    local k8s_stores=""
    
    # Run benchmarks for each store
    for store in $STORES; do
        log_section "Benchmarking: $store"
        
        if [[ "$SKIP_K8S" == "true" && "$store" != "sqlite" ]]; then
            log_warn "Skipping $store (--skip-k8s enabled)"
            continue
        fi
        
        case $store in
            sqlite)
                if [[ "$SKIP_K8S" == "true" ]]; then
                    run_local_benchmark "$store"
                else
                    delete_existing_jobs "$store"
                    create_job "$store"
                    k8s_stores="$k8s_stores $store"
                fi
                ;;
            redis|postgres|dynamodb)
                delete_existing_jobs "$store"
                create_job "$store"
                k8s_stores="$k8s_stores $store"
                ;;
            *)
                log_error "Unknown store: $store"
                ;;
        esac
    done
    
    # Wait for all K8s jobs
    if [[ -n "$k8s_stores" ]]; then
        log_section "Waiting for K8s Jobs"
        for store in $k8s_stores; do
            wait_for_job "$store" || log_warn "Job $store may have failed"
        done
        
        # Fetch results
        log_section "Collecting Results"
        create_results_reader
        for store in $k8s_stores; do
            fetch_results "$store"
        done
        cleanup_results_reader
    fi
    
    # Generate charts
    if [[ "$SKIP_CHARTS" != "true" ]]; then
        generate_charts
    fi
    
    # Print summary
    print_summary
    
    log_header "Benchmark Complete"
}

# Run main
main "$@"
