#!/usr/bin/env python3
"""
Compare benchmark results across multiple online stores.

Generates:
- Combined comparison charts
- Side-by-side latency tables
- Function breakdown comparison
- Markdown summary report

Usage:
    python compare_stores.py \
        --dirs results_sqlite results_redis results_dynamodb \
        --names sqlite redis dynamodb \
        --output comparison
"""
import argparse
import json
import os
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

STORE_COLORS = {
    'sqlite': '#3498db',
    'redis': '#e74c3c',
    'dynamodb': '#f39c12',
    'postgres': '#2ecc71',
}


def load_results(result_dirs: List[str], store_names: List[str]) -> Dict[str, Dict]:
    """Load results from multiple directories."""
    all_results = {}
    
    for dir_path, name in zip(result_dirs, store_names):
        json_path = os.path.join(dir_path, "benchmark_results.json")
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                all_results[name] = json.load(f)
            print(f"Loaded: {json_path}")
        else:
            print(f"Warning: {json_path} not found")
    
    return all_results


def build_comparison_df(all_results: Dict[str, Dict], test_type: str = "latency") -> pd.DataFrame:
    """Build comparison DataFrame from results."""
    rows = []
    
    for store, data in all_results.items():
        results = data.get(test_type, [])
        for r in results:
            rows.append({
                'store': store,
                'features': r.get('num_features', 0),
                'entities': r.get('num_entities', 0),
                'fvs': r.get('num_feature_views', 1),
                'transform': r.get('transformation_mode', 'none'),
                'p50': r.get('p50', 0),
                'p95': r.get('p95', 0),
                'p99': r.get('p99', 0),
                'online_read_pct': r.get('online_read_pct', 0),
                'protobuf_pct': r.get('protobuf_convert_pct', 0),
                'sla_pass': r.get('sla_pass', False),
            })
    
    return pd.DataFrame(rows)


def chart_latency_comparison(df: pd.DataFrame, output_dir: str, features: int = None):
    """Bar chart comparing p99 latency across stores."""
    if not HAS_MATPLOTLIB:
        return
    
    if features:
        df = df[df['features'] == features]
    
    stores = df['store'].unique()
    entities = sorted(df['entities'].unique())
    
    fig, ax = plt.subplots(figsize=(12, 7))
    x = np.arange(len(entities))
    width = 0.8 / len(stores)
    
    for i, store in enumerate(stores):
        store_df = df[df['store'] == store]
        values = []
        for e in entities:
            row = store_df[store_df['entities'] == e]
            values.append(row['p99'].values[0] if len(row) > 0 else 0)
        
        color = STORE_COLORS.get(store, '#95a5a6')
        offset = (i - len(stores)/2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=store.upper(), color=color, alpha=0.8)
        
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                       f'{val:.0f}', ha='center', va='bottom', fontsize=8)
    
    ax.axhline(y=60, color='red', linestyle='--', linewidth=2, label='SLA (60ms)')
    
    ax.set_xlabel('Entity Count', fontsize=12)
    ax.set_ylabel('P99 Latency (ms)', fontsize=12)
    title = 'Online Store Comparison - P99 Latency'
    if features:
        title += f' ({features} features)'
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(entities)
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    suffix = f'_{features}f' if features else ''
    plt.savefig(os.path.join(output_dir, f'comparison_p99_latency{suffix}.png'), dpi=150)
    plt.close()
    print(f"Saved: comparison_p99_latency{suffix}.png")


def chart_breakdown_comparison(df: pd.DataFrame, output_dir: str):
    """Pie charts comparing function breakdown across stores."""
    if not HAS_MATPLOTLIB:
        return
    
    stores = df['store'].unique()
    
    # Get largest entity count for comparison
    max_entities = df['entities'].max()
    df_filtered = df[df['entities'] == max_entities]
    
    fig, axes = plt.subplots(1, len(stores), figsize=(5 * len(stores), 5))
    if len(stores) == 1:
        axes = [axes]
    
    colors = ['#3498db', '#e74c3c', '#f39c12', '#95a5a6']
    labels = ['online_read', 'protobuf', 'entity_serial', 'other']
    
    for ax, store in zip(axes, stores):
        store_df = df_filtered[df_filtered['store'] == store]
        if len(store_df) == 0:
            continue
        
        row = store_df.iloc[0]
        values = [
            row.get('online_read_pct', 0),
            row.get('protobuf_pct', 0),
            0,  # entity_serial not always present
            100 - row.get('online_read_pct', 0) - row.get('protobuf_pct', 0)
        ]
        
        # Filter out zeros
        non_zero = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
        if non_zero:
            labels_nz, values_nz, colors_nz = zip(*non_zero)
            ax.pie(values_nz, labels=labels_nz, colors=colors_nz, autopct='%1.0f%%', startangle=90)
        
        ax.set_title(f'{store.upper()}\n({max_entities} entities)', fontsize=12, fontweight='bold')
    
    plt.suptitle('Function Breakdown Comparison', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: comparison_breakdown.png")


def chart_fv_scaling_comparison(all_results: Dict[str, Dict], output_dir: str):
    """Compare FV scaling across stores."""
    if not HAS_MATPLOTLIB:
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for store, data in all_results.items():
        fv_results = data.get('fv_scaling', [])
        if not fv_results:
            continue
        
        fv_counts = [r['num_feature_views'] for r in fv_results]
        p99s = [r['p99'] for r in fv_results]
        
        color = STORE_COLORS.get(store, '#95a5a6')
        ax.plot(fv_counts, p99s, marker='o', linewidth=2, markersize=8,
               label=store.upper(), color=color)
    
    ax.axhline(y=60, color='red', linestyle='--', linewidth=2, label='SLA (60ms)')
    
    ax.set_xlabel('Number of Feature Views', fontsize=12)
    ax.set_ylabel('P99 Latency (ms)', fontsize=12)
    ax.set_title('Feature View Scaling Comparison', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_fv_scaling.png'), dpi=150)
    plt.close()
    print("Saved: comparison_fv_scaling.png")


def chart_throughput_comparison(all_results: Dict[str, Dict], output_dir: str):
    """Compare throughput across stores."""
    if not HAS_MATPLOTLIB:
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for store, data in all_results.items():
        tp_results = data.get('throughput', [])
        if not tp_results:
            continue
        
        workers = [r['workers'] for r in tp_results]
        rph = [r['rph'] for r in tp_results]
        
        color = STORE_COLORS.get(store, '#95a5a6')
        ax.plot(workers, [r/1000 for r in rph], marker='s', linewidth=2, markersize=8,
               label=store.upper(), color=color)
    
    ax.axhline(y=3000, color='red', linestyle='--', linewidth=2, label='Target (3M RPH)')
    
    ax.set_xlabel('Worker Count', fontsize=12)
    ax.set_ylabel('Throughput (K RPH)', fontsize=12)
    ax.set_title('Throughput Comparison', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_throughput.png'), dpi=150)
    plt.close()
    print("Saved: comparison_throughput.png")


def generate_markdown_report(all_results: Dict[str, Dict], output_dir: str):
    """Generate comparison markdown report."""
    
    report = """# Online Store Comparison Report

## Latency Comparison (P99)

| Store | 1e | 10e | 50e | 100e | 500e | SLA Pass Rate |
|-------|-----|------|------|-------|-------|---------------|
"""
    
    for store, data in all_results.items():
        results = data.get('latency', [])
        row = f"| {store.upper()} |"
        
        entities = [1, 10, 50, 100, 500]
        pass_count = 0
        total_count = 0
        
        for e in entities:
            match = [r for r in results if r.get('num_entities') == e]
            if match:
                p99 = match[0].get('p99', 0)
                row += f" {p99:.0f}ms |"
                if match[0].get('sla_pass', False):
                    pass_count += 1
                total_count += 1
            else:
                row += " - |"
        
        pass_rate = (pass_count / total_count * 100) if total_count > 0 else 0
        row += f" {pass_rate:.0f}% |"
        report += row + "\n"
    
    report += """
## Feature View Scaling

| Store | 1 FV | 10 FVs | 50 FVs | 100 FVs |
|-------|------|--------|--------|---------|
"""
    
    for store, data in all_results.items():
        results = data.get('fv_scaling', [])
        row = f"| {store.upper()} |"
        
        for fv_count in [1, 10, 50, 100]:
            match = [r for r in results if r.get('num_feature_views') == fv_count]
            if match:
                p99 = match[0].get('p99', 0)
                sla = "✅" if match[0].get('sla_pass', False) else "❌"
                row += f" {p99:.0f}ms {sla} |"
            else:
                row += " - |"
        
        report += row + "\n"
    
    report += """
## Throughput

| Store | 1 Worker | 10 Workers | 20 Workers | Peak RPH |
|-------|----------|------------|------------|----------|
"""
    
    for store, data in all_results.items():
        results = data.get('throughput', [])
        row = f"| {store.upper()} |"
        
        for workers in [1, 10, 20]:
            match = [r for r in results if r.get('workers') == workers]
            if match:
                rps = match[0].get('rps', 0)
                row += f" {rps:.0f} RPS |"
            else:
                row += " - |"
        
        if results:
            peak = max(r.get('rph', 0) for r in results)
            pct = (peak / 3_000_000) * 100
            row += f" {peak:,} ({pct:.0f}%) |"
        else:
            row += " - |"
        
        report += row + "\n"
    
    report += """
## Summary

"""
    
    # Add per-store summary
    for store, data in all_results.items():
        summary = data.get('summary', {})
        report += f"### {store.upper()}\n"
        report += f"- Feast Version: {summary.get('feast_version', 'unknown')}\n"
        report += f"- Total Tests: {summary.get('total_tests', 0)}\n"
        report += f"- SLA Pass Rate: {summary.get('sla_pass_rate', 0):.1f}%\n\n"
    
    output_path = os.path.join(output_dir, 'comparison_report.md')
    with open(output_path, 'w') as f:
        f.write(report)
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare benchmark results across stores")
    parser.add_argument("--dirs", nargs='+', required=True,
                       help="Result directories to compare")
    parser.add_argument("--names", nargs='+', required=True,
                       help="Store names for each directory")
    parser.add_argument("--output", default="comparison",
                       help="Output directory for comparison results")
    
    args = parser.parse_args()
    
    if len(args.dirs) != len(args.names):
        print("Error: --dirs and --names must have same length")
        return
    
    os.makedirs(args.output, exist_ok=True)
    
    print("=" * 60)
    print("ONLINE STORE COMPARISON")
    print("=" * 60)
    
    # Load results
    all_results = load_results(args.dirs, args.names)
    
    if not all_results:
        print("No results found!")
        return
    
    # Build comparison DataFrames
    latency_df = build_comparison_df(all_results, 'latency')
    
    # Generate charts
    if HAS_MATPLOTLIB:
        print("\nGenerating charts...")
        
        # Latency comparison
        if not latency_df.empty:
            chart_latency_comparison(latency_df, args.output)
            chart_breakdown_comparison(latency_df, args.output)
            
            # Per feature count if multiple
            feature_counts = latency_df['features'].unique()
            if len(feature_counts) > 1:
                for f in feature_counts:
                    chart_latency_comparison(latency_df, args.output, features=f)
        
        # FV scaling
        chart_fv_scaling_comparison(all_results, args.output)
        
        # Throughput
        chart_throughput_comparison(all_results, args.output)
    
    # Generate markdown report
    generate_markdown_report(all_results, args.output)
    
    # Save combined CSV
    if not latency_df.empty:
        csv_path = os.path.join(args.output, 'all_stores_latency.csv')
        latency_df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")
    
    print("\n" + "=" * 60)
    print("COMPARISON COMPLETE")
    print(f"Results: {args.output}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
