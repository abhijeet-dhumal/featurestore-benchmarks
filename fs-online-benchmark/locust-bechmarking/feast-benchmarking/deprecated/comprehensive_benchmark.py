#!/usr/bin/env python3
"""
[DEPRECATED] Use unified_benchmark.py instead.

This script is kept for backwards compatibility.
For new benchmarks, run:
    python unified_benchmark.py --preset full --store sqlite

---

Comprehensive Feast Benchmark with Function-Level Profiling.

Generates publication-ready metrics and charts for:
- Latency breakdown by function (online_read, protobuf_convert, etc.)
- Test matrix: features × entities × stores × transformations
- Visual charts (PNG/SVG) for blogs/docs

Usage:
    python comprehensive_benchmark.py --store redis --output results/
    python comprehensive_benchmark.py --store dynamodb --features 200 --output results/
"""
import argparse
import cProfile
import io
import json
import os
import pstats
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import statistics

import pandas as pd
import numpy as np

# Optional visualization imports
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not installed. Charts will be skipped.")


@dataclass
class FunctionTiming:
    """Timing data for a single function."""
    name: str
    total_time_ms: float
    calls: int
    time_per_call_ms: float
    percent_of_total: float


@dataclass
class RequestProfile:
    """Profile of a single request."""
    total_time_ms: float
    online_read_ms: float
    protobuf_convert_ms: float
    entity_serialization_ms: float
    other_ms: float
    function_breakdown: List[FunctionTiming]


@dataclass 
class BenchmarkResult:
    """Complete benchmark result for one configuration."""
    # Configuration
    num_features: int
    num_entities: int
    num_feature_views: int
    num_feature_services: int
    online_store: str
    transformation_mode: Optional[str]  # None, "python", "pandas"
    server_type: str  # "sdk", "fastapi"
    
    # Latency metrics (ms)
    p50: float
    p95: float
    p99: float
    mean: float
    std: float
    min: float
    max: float
    
    # Throughput
    requests_per_second: float
    
    # Function breakdown (averages)
    online_read_pct: float
    protobuf_convert_pct: float
    entity_serialization_pct: float
    transformation_pct: float
    other_pct: float
    
    # Raw data
    latencies: List[float]
    profiles: List[Dict]
    
    # Metadata
    timestamp: str
    feast_version: str
    python_version: str


class FeastProfiler:
    """Profile Feast requests with function-level timing."""
    
    def __init__(self, feature_store):
        self.fs = feature_store
        self.profiles = []
    
    def profile_request(
        self, 
        features: List[str], 
        entity_rows: List[Dict]
    ) -> RequestProfile:
        """Profile a single get_online_features request."""
        
        # Use cProfile for function-level timing
        profiler = cProfile.Profile()
        
        start = time.perf_counter()
        profiler.enable()
        result = self.fs.get_online_features(
            features=features,
            entity_rows=entity_rows
        )
        profiler.disable()
        total_time = (time.perf_counter() - start) * 1000
        
        # Parse profile stats
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumulative')
        
        # Extract key function timings
        function_times = {}
        for func, (cc, nc, tt, ct, callers) in stats.stats.items():
            filename, lineno, funcname = func
            time_ms = ct * 1000  # cumulative time in ms
            function_times[funcname] = {
                'time_ms': time_ms,
                'calls': nc,
                'time_per_call_ms': (ct / nc * 1000) if nc > 0 else 0
            }
        
        # Identify key functions
        online_read_ms = function_times.get('online_read', {}).get('time_ms', 0)
        if online_read_ms == 0:
            online_read_ms = function_times.get('_get_online_features', {}).get('time_ms', 0)
        
        protobuf_ms = function_times.get('_convert_rows_to_protobuf', {}).get('time_ms', 0)
        entity_serial_ms = function_times.get('serialize_entity_key', {}).get('time_ms', 0)
        
        other_ms = total_time - online_read_ms - protobuf_ms - entity_serial_ms
        if other_ms < 0:
            other_ms = 0
        
        # Build function breakdown
        breakdown = []
        for name, data in sorted(
            function_times.items(), 
            key=lambda x: x[1]['time_ms'], 
            reverse=True
        )[:15]:
            breakdown.append(FunctionTiming(
                name=name,
                total_time_ms=data['time_ms'],
                calls=data['calls'],
                time_per_call_ms=data['time_per_call_ms'],
                percent_of_total=(data['time_ms'] / total_time * 100) if total_time > 0 else 0
            ))
        
        profile = RequestProfile(
            total_time_ms=total_time,
            online_read_ms=online_read_ms,
            protobuf_convert_ms=protobuf_ms,
            entity_serialization_ms=entity_serial_ms,
            other_ms=other_ms,
            function_breakdown=breakdown
        )
        
        self.profiles.append(profile)
        return profile


class ComprehensiveBenchmark:
    """Run comprehensive benchmarks across all dimensions."""
    
    def __init__(self, repo_path: str, output_dir: str):
        self.repo_path = repo_path
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        from feast import FeatureStore
        self.fs = FeatureStore(repo_path=repo_path)
        self.profiler = FeastProfiler(self.fs)
        
        # Get Feast version
        import feast
        self.feast_version = feast.__version__
        
        import sys
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def run_single_config(
        self,
        num_features: int,
        num_entities: int,
        num_iterations: int = 20,
        warmup: int = 3,
        transformation_mode: Optional[str] = None
    ) -> BenchmarkResult:
        """Run benchmark for a single configuration."""
        
        features = [f"bench_fv:feature_{i}" for i in range(num_features)]
        entity_rows = [{"user_id": f"user_{i}"} for i in range(num_entities)]
        
        # Warmup
        for _ in range(warmup):
            self.fs.get_online_features(features=features, entity_rows=entity_rows)
        
        # Benchmark with profiling
        latencies = []
        profiles = []
        
        for i in range(num_iterations):
            profile = self.profiler.profile_request(features, entity_rows)
            latencies.append(profile.total_time_ms)
            profiles.append(asdict(profile))
        
        # Calculate statistics
        latencies_sorted = sorted(latencies)
        
        # Calculate average breakdown percentages
        avg_online_read_pct = statistics.mean(
            [p['online_read_ms'] / p['total_time_ms'] * 100 
             for p in profiles if p['total_time_ms'] > 0]
        )
        avg_protobuf_pct = statistics.mean(
            [p['protobuf_convert_ms'] / p['total_time_ms'] * 100 
             for p in profiles if p['total_time_ms'] > 0]
        )
        avg_entity_pct = statistics.mean(
            [p['entity_serialization_ms'] / p['total_time_ms'] * 100 
             for p in profiles if p['total_time_ms'] > 0]
        )
        
        result = BenchmarkResult(
            num_features=num_features,
            num_entities=num_entities,
            num_feature_views=1,
            num_feature_services=0,
            online_store=self._get_store_type(),
            transformation_mode=transformation_mode,
            server_type="sdk",
            p50=latencies_sorted[int(len(latencies_sorted) * 0.5)],
            p95=latencies_sorted[int(len(latencies_sorted) * 0.95)],
            p99=latencies_sorted[int(len(latencies_sorted) * 0.99)] if len(latencies_sorted) >= 100 else latencies_sorted[-1],
            mean=statistics.mean(latencies),
            std=statistics.stdev(latencies) if len(latencies) > 1 else 0,
            min=min(latencies),
            max=max(latencies),
            requests_per_second=1000 / statistics.mean(latencies) if statistics.mean(latencies) > 0 else 0,
            online_read_pct=avg_online_read_pct,
            protobuf_convert_pct=avg_protobuf_pct,
            entity_serialization_pct=avg_entity_pct,
            transformation_pct=0,  # TODO: measure if transformation_mode set
            other_pct=100 - avg_online_read_pct - avg_protobuf_pct - avg_entity_pct,
            latencies=latencies,
            profiles=profiles,
            timestamp=datetime.now().isoformat(),
            feast_version=self.feast_version,
            python_version=self.python_version
        )
        
        return result
    
    def _get_store_type(self) -> str:
        """Get online store type from config."""
        try:
            config = self.fs.config
            return config.online_store.type
        except:
            return "unknown"
    
    def run_test_matrix(
        self,
        feature_counts: List[int] = [50, 200],
        entity_counts: List[int] = [1, 10, 50, 100, 500],
        iterations: int = 20
    ) -> List[BenchmarkResult]:
        """Run full test matrix."""
        
        results = []
        total = len(feature_counts) * len(entity_counts)
        current = 0
        
        for num_features in feature_counts:
            for num_entities in entity_counts:
                current += 1
                print(f"\n[{current}/{total}] Testing {num_features}f × {num_entities}e...")
                
                try:
                    result = self.run_single_config(
                        num_features=num_features,
                        num_entities=num_entities,
                        num_iterations=iterations
                    )
                    results.append(result)
                    
                    # Print summary
                    print(f"  p50: {result.p50:.2f}ms | p95: {result.p95:.2f}ms | p99: {result.p99:.2f}ms")
                    print(f"  Breakdown: online_read={result.online_read_pct:.1f}% | "
                          f"protobuf={result.protobuf_convert_pct:.1f}% | "
                          f"entity_serial={result.entity_serialization_pct:.1f}%")
                    
                except Exception as e:
                    print(f"  ERROR: {e}")
        
        return results
    
    def save_results(self, results: List[BenchmarkResult], prefix: str = "benchmark"):
        """Save results to JSON and CSV."""
        
        # JSON (full data)
        json_path = os.path.join(self.output_dir, f"{prefix}_results.json")
        json_data = [asdict(r) for r in results]
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)
        print(f"\nSaved JSON: {json_path}")
        
        # CSV (summary)
        csv_data = []
        for r in results:
            csv_data.append({
                'features': r.num_features,
                'entities': r.num_entities,
                'store': r.online_store,
                'p50_ms': round(r.p50, 2),
                'p95_ms': round(r.p95, 2),
                'p99_ms': round(r.p99, 2),
                'mean_ms': round(r.mean, 2),
                'rps': round(r.requests_per_second, 2),
                'online_read_pct': round(r.online_read_pct, 1),
                'protobuf_pct': round(r.protobuf_convert_pct, 1),
                'entity_serial_pct': round(r.entity_serialization_pct, 1),
            })
        
        csv_path = os.path.join(self.output_dir, f"{prefix}_summary.csv")
        pd.DataFrame(csv_data).to_csv(csv_path, index=False)
        print(f"Saved CSV: {csv_path}")
        
        # Markdown table
        md_path = os.path.join(self.output_dir, f"{prefix}_report.md")
        self._generate_markdown_report(results, md_path)
        print(f"Saved Markdown: {md_path}")
        
        return json_path, csv_path, md_path
    
    def _generate_markdown_report(self, results: List[BenchmarkResult], output_path: str):
        """Generate markdown report for docs/blogs."""
        
        store = results[0].online_store if results else "unknown"
        
        report = f"""# Feast Performance Benchmark Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Feast Version:** {self.feast_version}  
**Online Store:** {store}  
**Python Version:** {self.python_version}

## Latency Results

| Features | Entities | p50 (ms) | p95 (ms) | p99 (ms) | RPS | SLA (60ms) |
|----------|----------|----------|----------|----------|-----|------------|
"""
        for r in results:
            sla = "✅ PASS" if r.p99 < 60 else "❌ FAIL"
            report += f"| {r.num_features} | {r.num_entities} | {r.p50:.2f} | {r.p95:.2f} | {r.p99:.2f} | {r.requests_per_second:.1f} | {sla} |\n"
        
        report += """
## Function-Level Breakdown (Average)

| Features | Entities | online_read | protobuf_convert | entity_serial | other |
|----------|----------|-------------|------------------|---------------|-------|
"""
        for r in results:
            report += f"| {r.num_features} | {r.num_entities} | {r.online_read_pct:.1f}% | {r.protobuf_convert_pct:.1f}% | {r.entity_serialization_pct:.1f}% | {r.other_pct:.1f}% |\n"
        
        report += """
## Key Findings

"""
        # Find bottleneck
        if results:
            r = results[-1]  # Largest config
            if r.protobuf_convert_pct > 30:
                report += f"- **Primary Bottleneck:** `_convert_rows_to_protobuf` consuming {r.protobuf_convert_pct:.1f}% of request time\n"
            if r.online_read_pct > 30:
                report += f"- **Secondary Bottleneck:** `online_read` consuming {r.online_read_pct:.1f}% of request time\n"
        
        report += """
## Methodology

- **Iterations:** 20 per configuration (3 warmup)
- **Profiling:** cProfile with cumulative timing
- **SLA Target:** 60ms p99 latency

"""
        
        with open(output_path, 'w') as f:
            f.write(report)
    
    def generate_charts(self, results: List[BenchmarkResult], prefix: str = "benchmark"):
        """Generate publication-ready charts."""
        
        if not HAS_MATPLOTLIB:
            print("Skipping charts (matplotlib not installed)")
            return
        
        # Chart 1: Latency by entity count
        self._chart_latency_by_entities(results, prefix)
        
        # Chart 2: Function breakdown (stacked bar)
        self._chart_function_breakdown(results, prefix)
        
        # Chart 3: Latency heatmap
        self._chart_latency_heatmap(results, prefix)
    
    def _chart_latency_by_entities(self, results: List[BenchmarkResult], prefix: str):
        """Line chart: Latency vs Entity Count."""
        
        store = results[0].online_store.upper() if results else "UNKNOWN"
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Group by feature count
        feature_groups = {}
        for r in results:
            key = r.num_features
            if key not in feature_groups:
                feature_groups[key] = {'entities': [], 'p50': [], 'p95': [], 'p99': []}
            feature_groups[key]['entities'].append(r.num_entities)
            feature_groups[key]['p50'].append(r.p50)
            feature_groups[key]['p95'].append(r.p95)
            feature_groups[key]['p99'].append(r.p99)
        
        colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c']
        markers = ['o', 's', '^', 'D']
        
        for i, (features, data) in enumerate(sorted(feature_groups.items())):
            color = colors[i % len(colors)]
            marker = markers[i % len(markers)]
            
            ax.plot(data['entities'], data['p99'], 
                   marker=marker, color=color, linewidth=2,
                   label=f'{features} features (p99)')
            ax.plot(data['entities'], data['p50'], 
                   marker=marker, color=color, linewidth=1, linestyle='--',
                   alpha=0.5, label=f'{features} features (p50)')
        
        # SLA line
        ax.axhline(y=60, color='red', linestyle=':', linewidth=2, label='SLA (60ms)')
        
        ax.set_xlabel('Number of Entities', fontsize=12)
        ax.set_ylabel('Latency (ms)', fontsize=12)
        ax.set_title(f'Feast Latency - {store} Online Store', fontsize=14, fontweight='bold')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_xscale('log')
        ax.set_yscale('log')
        
        # Add store watermark
        ax.text(0.98, 0.02, f'Store: {store}', transform=ax.transAxes, 
                fontsize=10, color='gray', ha='right', va='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, f"{prefix}_{store.lower()}_latency.png")
        plt.savefig(chart_path, dpi=150)
        plt.close()
        print(f"Saved chart: {chart_path}")
    
    def _chart_function_breakdown(self, results: List[BenchmarkResult], prefix: str):
        """Stacked bar chart: Function breakdown."""
        
        store = results[0].online_store.upper() if results else "UNKNOWN"
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        labels = [f"{r.num_features}f×{r.num_entities}e" for r in results]
        online_read = [r.online_read_pct for r in results]
        protobuf = [r.protobuf_convert_pct for r in results]
        entity_serial = [r.entity_serialization_pct for r in results]
        other = [r.other_pct for r in results]
        
        x = np.arange(len(labels))
        width = 0.6
        
        ax.bar(x, online_read, width, label='online_read', color='#3498db')
        ax.bar(x, protobuf, width, bottom=online_read, label='protobuf_convert', color='#e74c3c')
        ax.bar(x, entity_serial, width, 
               bottom=[a+b for a,b in zip(online_read, protobuf)], 
               label='entity_serialization', color='#f39c12')
        ax.bar(x, other, width, 
               bottom=[a+b+c for a,b,c in zip(online_read, protobuf, entity_serial)], 
               label='other', color='#95a5a6')
        
        ax.set_xlabel('Configuration (features × entities)', fontsize=12)
        ax.set_ylabel('Percentage of Total Time', fontsize=12)
        ax.set_title(f'Function Breakdown - {store} Online Store', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.legend(loc='upper right')
        ax.set_ylim(0, 100)
        
        # Add store watermark
        ax.text(0.98, 0.98, f'Store: {store}', transform=ax.transAxes, 
                fontsize=10, color='gray', ha='right', va='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, f"{prefix}_{store.lower()}_breakdown.png")
        plt.savefig(chart_path, dpi=150)
        plt.close()
        print(f"Saved chart: {chart_path}")
    
    def _chart_latency_heatmap(self, results: List[BenchmarkResult], prefix: str):
        """Heatmap: Features vs Entities latency."""
        
        store = results[0].online_store.upper() if results else "UNKNOWN"
        
        # Build matrix
        features_set = sorted(set(r.num_features for r in results))
        entities_set = sorted(set(r.num_entities for r in results))
        
        matrix = np.zeros((len(features_set), len(entities_set)))
        
        for r in results:
            i = features_set.index(r.num_features)
            j = entities_set.index(r.num_entities)
            matrix[i, j] = r.p99
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        im = ax.imshow(matrix, cmap='RdYlGn_r', aspect='auto')
        
        ax.set_xticks(np.arange(len(entities_set)))
        ax.set_yticks(np.arange(len(features_set)))
        ax.set_xticklabels(entities_set)
        ax.set_yticklabels(features_set)
        ax.set_xlabel('Number of Entities', fontsize=12)
        ax.set_ylabel('Number of Features', fontsize=12)
        ax.set_title(f'P99 Latency Heatmap - {store} (ms)', fontsize=14, fontweight='bold')
        
        # Add text annotations
        for i in range(len(features_set)):
            for j in range(len(entities_set)):
                value = matrix[i, j]
                color = 'white' if value > 100 else 'black'
                ax.text(j, i, f'{value:.0f}', ha='center', va='center', color=color, fontsize=10)
        
        cbar = ax.figure.colorbar(im, ax=ax)
        cbar.ax.set_ylabel('Latency (ms)', rotation=-90, va='bottom')
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, f"{prefix}_{store.lower()}_heatmap.png")
        plt.savefig(chart_path, dpi=150)
        plt.close()
        print(f"Saved chart: {chart_path}")


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Feast Benchmark")
    parser.add_argument("--repo-path", default="/tmp/feast_benchmark",
                       help="Feast repository path")
    parser.add_argument("--output", default="results",
                       help="Output directory for results")
    parser.add_argument("--features", nargs='+', type=int, default=[50, 200],
                       help="Feature counts to test")
    parser.add_argument("--entities", nargs='+', type=int, default=[1, 10, 50, 100, 500],
                       help="Entity counts to test")
    parser.add_argument("--iterations", type=int, default=20,
                       help="Iterations per configuration")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("COMPREHENSIVE FEAST BENCHMARK")
    print("=" * 70)
    print(f"Repo: {args.repo_path}")
    print(f"Features: {args.features}")
    print(f"Entities: {args.entities}")
    print(f"Iterations: {args.iterations}")
    print("=" * 70)
    
    benchmark = ComprehensiveBenchmark(args.repo_path, args.output)
    
    # Run test matrix
    results = benchmark.run_test_matrix(
        feature_counts=args.features,
        entity_counts=args.entities,
        iterations=args.iterations
    )
    
    # Save results
    benchmark.save_results(results)
    
    # Generate charts
    benchmark.generate_charts(results)
    
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
