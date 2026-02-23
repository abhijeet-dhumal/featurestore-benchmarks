#!/usr/bin/env python3
"""
Chart Generator - Creates only the 4 curated charts for blog/team sharing.

Output:
  01_latency_comparison.png    - P99 latency grouped bars with SLA line
  02_scaling_behavior.png      - Min to max entity scaling (slope chart)
  03_bottleneck_breakdown.png  - Time breakdown waterfall
  04_sla_compliance.png        - SLA pass/fail bullet chart
"""
import argparse
import json
import os
from typing import Dict, List

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Style
plt.style.use('seaborn-v0_8-whitegrid')
COLORS = {
    'sqlite': '#2ecc71',    # Green
    'redis': '#e74c3c',     # Red
    'dynamodb': '#f39c12',  # Orange
    'postgres': '#3498db',  # Blue
}
SLA_MS = 60
SLA_COLOR = '#c0392b'


def load_results(result_dirs: List[str], names: List[str]) -> Dict[str, Dict]:
    """Load benchmark results from directories."""
    results = {}
    for dir_path, name in zip(result_dirs, names):
        json_path = os.path.join(dir_path, "benchmark_results.json")
        if os.path.exists(json_path):
            with open(json_path) as f:
                results[name] = json.load(f)
    return results


def chart_latency_comparison(results: Dict, output_dir: str):
    """
    01 - Grouped bar chart comparing p99 latency across stores.
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    
    all_entities = set()
    for data in results.values():
        for r in data.get('latency', []):
            all_entities.add(r['num_entities'])
    entities = sorted(all_entities)
    
    stores = list(results.keys())
    n_stores = len(stores)
    bar_width = 0.8 / n_stores
    
    for i, store in enumerate(stores):
        data = results[store]
        latency_map = {r['num_entities']: r['p99'] for r in data.get('latency', [])}
        
        x_pos = np.arange(len(entities)) + i * bar_width - (n_stores - 1) * bar_width / 2
        values = [latency_map.get(e, 0) for e in entities]
        
        bars = ax.bar(x_pos, values, bar_width * 0.9,
                     label=store.upper(),
                     color=COLORS.get(store, '#95a5a6'),
                     edgecolor='white', linewidth=1, zorder=3)
        
        for bar, val in zip(bars, values):
            if val > 0:
                color = 'green' if val < SLA_MS else 'red'
                ax.annotate(f'{val:.0f}',
                           xy=(bar.get_x() + bar.get_width()/2, bar.get_height() + 5),
                           ha='center', va='bottom', fontsize=9, fontweight='bold', color=color)
    
    ax.axhline(y=SLA_MS, color=SLA_COLOR, linestyle='--', linewidth=2.5, zorder=4)
    ax.fill_between([-0.5, len(entities) - 0.5], 0, SLA_MS, alpha=0.1, color='green', zorder=1)
    ax.text(len(entities) - 0.6, SLA_MS + 10, f'SLA: {SLA_MS}ms', 
           fontsize=11, color=SLA_COLOR, fontweight='bold', ha='right')
    
    ax.set_xlabel('Entity Count', fontsize=13, fontweight='bold')
    ax.set_ylabel('p99 Latency (ms)', fontsize=13, fontweight='bold')
    ax.set_title('P99 Latency by Entity Count\nGrouped by Online Store', fontsize=15, fontweight='bold', pad=20)
    ax.set_xticks(range(len(entities)))
    ax.set_xticklabels([str(e) for e in entities], fontsize=11)
    ax.legend(loc='upper left', fontsize=11, framealpha=0.95)
    ax.set_xlim(-0.5, len(entities) - 0.5)
    ax.grid(axis='y', alpha=0.3, zorder=0)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '01_latency_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 01_latency_comparison.png")


def chart_scaling_behavior(results: Dict, output_dir: str):
    """
    02 - Slope chart showing latency scaling from min to max entities.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if len(latency_data) < 2:
            continue
        
        sorted_data = sorted(latency_data, key=lambda x: x['num_entities'])
        min_e, max_e = sorted_data[0], sorted_data[-1]
        color = COLORS.get(store, '#95a5a6')
        
        ax.plot([0, 1], [min_e['p99'], max_e['p99']], 
               color=color, linewidth=3, marker='o', markersize=12,
               markerfacecolor='white', markeredgewidth=3, label=store.upper())
        
        ax.text(-0.05, min_e['p99'], f"{min_e['p99']:.0f}ms",
               ha='right', va='center', fontsize=11, fontweight='bold', color=color)
        ax.text(1.05, max_e['p99'], f"{max_e['p99']:.0f}ms",
               ha='left', va='center', fontsize=11, fontweight='bold', color=color)
    
    ax.axhline(y=SLA_MS, color=SLA_COLOR, linestyle='--', linewidth=2, alpha=0.7)
    ax.text(0.5, SLA_MS + 20, f'SLA: {SLA_MS}ms', ha='center', fontsize=11,
           color=SLA_COLOR, fontweight='bold')
    
    first_data = list(results.values())[0].get('latency', [])
    if first_data:
        sorted_data = sorted(first_data, key=lambda x: x['num_entities'])
        ax.set_xticks([0, 1])
        ax.set_xticklabels([f"{sorted_data[0]['num_entities']} entities",
                           f"{sorted_data[-1]['num_entities']} entities"], fontsize=12, fontweight='bold')
    
    ax.set_ylabel('p99 Latency (ms)', fontsize=13, fontweight='bold')
    ax.set_title('Latency Scaling: Min to Max Entities\n(Slope = Scaling Behavior)', fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='upper left', fontsize=11)
    ax.set_xlim(-0.2, 1.2)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '02_scaling_behavior.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 02_scaling_behavior.png")


def chart_bottleneck_breakdown(results: Dict, output_dir: str):
    """
    03 - Waterfall chart showing time breakdown (online_read, protobuf, other).
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    stores = list(results.keys())
    breakdown_data = []
    
    for store in stores:
        data = results[store]
        latency_data = data.get('latency', [])
        if latency_data:
            r = max(latency_data, key=lambda x: x['num_entities'])
            total = r['p99']
            online_read = total * r.get('online_read_pct', 0) / 100
            protobuf = total * r.get('protobuf_convert_pct', 0) / 100
            other = total - online_read - protobuf
            breakdown_data.append({
                'store': store, 'entities': r['num_entities'], 'total': total,
                'online_read': online_read, 'protobuf': protobuf, 'other': other
            })
    
    if not breakdown_data:
        return
    
    y_pos = np.arange(len(breakdown_data))
    lefts = [0] * len(breakdown_data)
    
    components = [
        ('online_read', 'Online Store Read', '#3498db'),
        ('protobuf', 'Protobuf Convert', '#e74c3c'),
        ('other', 'Other Processing', '#95a5a6')
    ]
    
    for key, label, color in components:
        values = [d[key] for d in breakdown_data]
        bars = ax.barh(y_pos, values, left=lefts, height=0.6,
                      label=label, color=color, edgecolor='white', linewidth=1)
        
        for i, (bar, val) in enumerate(zip(bars, values)):
            if val > 20:
                ax.text(lefts[i] + val/2, i, f'{val:.0f}ms',
                       ha='center', va='center', fontsize=10, fontweight='bold', color='white')
        
        lefts = [l + v for l, v in zip(lefts, values)]
    
    for i, d in enumerate(breakdown_data):
        ax.text(d['total'] + 10, i, f"{d['total']:.0f}ms total",
               ha='left', va='center', fontsize=11, fontweight='bold',
               color='green' if d['total'] < SLA_MS else 'red')
    
    ax.axvline(x=SLA_MS, color=SLA_COLOR, linestyle='--', linewidth=2.5, zorder=5)
    ax.text(SLA_MS, len(breakdown_data) - 0.3, f'SLA: {SLA_MS}ms',
           fontsize=10, color=SLA_COLOR, fontweight='bold', rotation=90, va='top')
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f"{d['store'].upper()}\n({d['entities']}e)" for d in breakdown_data], fontsize=11)
    ax.set_xlabel('Time (ms)', fontsize=13, fontweight='bold')
    ax.set_title('Request Time Breakdown\n(Largest Entity Count)', fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.95)
    ax.grid(axis='x', alpha=0.3, zorder=0)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '03_bottleneck_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 03_bottleneck_breakdown.png")


def chart_sla_compliance(results: Dict, output_dir: str):
    """
    04 - Bullet chart showing SLA pass/fail for each store.
    """
    fig, axes = plt.subplots(len(results), 1, figsize=(12, 3 * len(results)))
    
    if len(results) == 1:
        axes = [axes]
    
    for ax, (store, data) in zip(axes, results.items()):
        latency_data = data.get('latency', [])
        if not latency_data:
            continue
        
        r = max(latency_data, key=lambda x: x['num_entities'])
        actual = r['p99']
        entities = r['num_entities']
        color = COLORS.get(store, '#95a5a6')
        
        # Background ranges
        ax.barh(0, SLA_MS * 3, height=0.8, color='#ffcccc', zorder=1)
        ax.barh(0, SLA_MS * 1.5, height=0.8, color='#ffffcc', zorder=2)
        ax.barh(0, SLA_MS, height=0.8, color='#ccffcc', zorder=3)
        
        # Actual bar
        ax.barh(0, actual, height=0.4, color=color, zorder=4, alpha=0.9)
        
        # Target marker
        ax.axvline(x=SLA_MS, color='black', linewidth=3, zorder=5)
        
        ax.text(actual + 10, 0, f'{actual:.0f}ms', 
               ha='left', va='center', fontsize=12, fontweight='bold',
               color='green' if actual < SLA_MS else 'red')
        
        status = 'PASS' if actual < SLA_MS else 'FAIL'
        ax.set_ylabel(f'{store.upper()}\n({entities}e)', fontsize=12, fontweight='bold', 
                     rotation=0, ha='right', va='center')
        ax.set_xlim(0, max(actual * 1.2, SLA_MS * 2))
        ax.set_ylim(-0.5, 0.5)
        ax.set_yticks([])
        ax.set_xlabel('p99 Latency (ms)' if ax == axes[-1] else '', fontsize=11)
        
        badge_color = '#27ae60' if actual < SLA_MS else '#e74c3c'
        ax.text(0.98, 0.5, status, transform=ax.transAxes, ha='right', va='top',
               fontsize=11, fontweight='bold', color='white',
               bbox=dict(boxstyle='round,pad=0.3', facecolor=badge_color, edgecolor='none'))
    
    legend_elements = [
        mpatches.Patch(facecolor='#ccffcc', label=f'Good (<{SLA_MS}ms)'),
        mpatches.Patch(facecolor='#ffffcc', label=f'Acceptable (<{int(SLA_MS*1.5)}ms)'),
        mpatches.Patch(facecolor='#ffcccc', label=f'Poor (>{int(SLA_MS*1.5)}ms)'),
        plt.Line2D([0], [0], color='black', linewidth=3, label='SLA Target')
    ]
    fig.legend(handles=legend_elements, loc='upper right', fontsize=10, bbox_to_anchor=(0.98, 0.98))
    
    fig.suptitle('SLA Compliance - Bullet Chart', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '04_sla_compliance.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 04_sla_compliance.png")


def main():
    parser = argparse.ArgumentParser(
        description="Generate curated benchmark charts (4 charts only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python generate_charts.py \\
      --dirs results/sqlite results/redis results/dynamodb \\
      --names sqlite redis dynamodb \\
      --output results/comparison
"""
    )
    parser.add_argument("--dirs", nargs='+', required=True, help="Result directories")
    parser.add_argument("--names", nargs='+', required=True, help="Store names")
    parser.add_argument("--output", default="results/comparison", help="Output directory")
    
    args = parser.parse_args()
    
    if len(args.dirs) != len(args.names):
        print("Error: --dirs and --names must have same length")
        return
    
    os.makedirs(args.output, exist_ok=True)
    
    print("=" * 60)
    print("CHART GENERATOR")
    print("=" * 60)
    
    results = load_results(args.dirs, args.names)
    
    if not results:
        print("No results found!")
        return
    
    print(f"Stores: {', '.join(results.keys())}")
    print(f"Output: {args.output}/")
    print("-" * 60)
    
    chart_latency_comparison(results, args.output)
    chart_scaling_behavior(results, args.output)
    chart_bottleneck_breakdown(results, args.output)
    chart_sla_compliance(results, args.output)
    
    print("-" * 60)
    print("Done! 4 charts generated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
