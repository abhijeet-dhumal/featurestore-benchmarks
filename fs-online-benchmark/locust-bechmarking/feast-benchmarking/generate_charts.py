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

# State Farm's actual SLA requirement
STATEFARM_SLA_MS = 60  # Fixed 60ms target
STATEFARM_ENTITIES = [50, 200]  # Their test entity counts
STATEFARM_FEATURES = 200  # Their feature count

SLA_COLOR = '#c0392b'
STATEFARM_COLOR = '#9b59b6'  # Purple for State Farm

# Exponential SLA model for comparison
SLA_BASE_MS = 20

def get_sla_target(num_entities: int) -> float:
    """
    Calculate exponential SLA target based on entity count.
    SLA(n) = base * (1 + log2(n) * sqrt(n) / 10)
    """
    import math
    if num_entities <= 1:
        return SLA_BASE_MS
    log_factor = math.log2(num_entities)
    sqrt_factor = math.sqrt(num_entities)
    return SLA_BASE_MS * (1 + log_factor * sqrt_factor / 10)

# Legacy flat SLA for reference
SLA_MS = 60


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
    01 - Grouped bar chart comparing p99 latency across stores (LOG SCALE).
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
        
        for j, (bar, val, ent) in enumerate(zip(bars, values, entities)):
            if val > 0:
                sla_target = get_sla_target(ent)
                color = 'green' if val < sla_target else 'red'
                # Position label above bar (log scale friendly)
                ax.annotate(f'{val:.0f}',
                           xy=(bar.get_x() + bar.get_width()/2, val),
                           xytext=(0, 5), textcoords='offset points',
                           ha='center', va='bottom', fontsize=9, fontweight='bold', color=color)
    
    # Use log scale for y-axis
    ax.set_yscale('log')
    
    # Draw exponential SLA markers for each entity group
    for idx, ent in enumerate(entities):
        sla_target = get_sla_target(ent)
        x_start = idx - 0.45
        x_end = idx + 0.45
        ax.hlines(y=sla_target, xmin=x_start, xmax=x_end, color=SLA_COLOR, 
                 linestyle='-', linewidth=2.5, zorder=4)
        ax.annotate(f'SLA:{sla_target:.0f}ms', xy=(x_end, sla_target), 
                   xytext=(3, 0), textcoords='offset points',
                   fontsize=8, color=SLA_COLOR, fontweight='bold', va='center')
    
    ax.set_xlabel('Entity Count', fontsize=13, fontweight='bold')
    ax.set_ylabel('p99 Latency (ms) - Log Scale', fontsize=13, fontweight='bold')
    ax.set_title('P99 Latency vs Exponential SLA Target\n(SLA scales with entity count)', fontsize=15, fontweight='bold', pad=20)
    ax.set_xticks(range(len(entities)))
    ax.set_xticklabels([str(e) for e in entities], fontsize=11)
    ax.legend(loc='upper left', fontsize=11, framealpha=0.95)
    ax.set_xlim(-0.5, len(entities) - 0.5)
    ax.set_ylim(10, None)  # Start from 10ms
    ax.grid(axis='y', alpha=0.3, zorder=0, which='both')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '01_latency_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 01_latency_comparison.png")


def chart_scaling_behavior(results: Dict, output_dir: str):
    """
    02 - Log-log scaling chart with EXPONENTIAL SLA target curve.
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if len(latency_data) < 2:
            continue
        
        sorted_data = sorted(latency_data, key=lambda x: x['num_entities'])
        entities = [d['num_entities'] for d in sorted_data]
        latencies = [d['p99'] for d in sorted_data]
        color = COLORS.get(store, '#95a5a6')
        
        # Plot all data points with connecting lines
        ax.plot(entities, latencies, 
               color=color, linewidth=3, marker='o', markersize=10,
               markerfacecolor='white', markeredgewidth=2.5, label=store.upper(), zorder=3)
        
        # Add labels for first and last points
        ax.annotate(f'{latencies[0]:.0f}ms', xy=(entities[0], latencies[0]),
                   xytext=(-10, 10), textcoords='offset points',
                   fontsize=10, fontweight='bold', color=color, ha='right')
        ax.annotate(f'{latencies[-1]:.0f}ms', xy=(entities[-1], latencies[-1]),
                   xytext=(10, 0), textcoords='offset points',
                   fontsize=10, fontweight='bold', color=color, ha='left')
    
    # Use log scale for both axes
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    # EXPONENTIAL SLA curve (not flat line!)
    x_sla = np.array([1, 2, 5, 10, 20, 50, 100, 200, 500])
    y_sla = np.array([get_sla_target(e) for e in x_sla])
    ax.plot(x_sla, y_sla, color=SLA_COLOR, linestyle='-', linewidth=3, zorder=4, label='SLA Target (exponential)')
    ax.fill_between(x_sla, 1, y_sla, alpha=0.15, color='green', zorder=1)
    
    # Add SLA values at key points
    for e, sla in [(1, get_sla_target(1)), (10, get_sla_target(10)), (100, get_sla_target(100)), (500, get_sla_target(500))]:
        ax.annotate(f'{sla:.0f}ms', xy=(e, sla), xytext=(0, -15), textcoords='offset points',
                   fontsize=9, color=SLA_COLOR, fontweight='bold', ha='center')
    
    ax.set_xlabel('Entity Count (Log Scale)', fontsize=13, fontweight='bold')
    ax.set_ylabel('p99 Latency (ms) - Log Scale', fontsize=13, fontweight='bold')
    ax.set_title('Latency Scaling vs Exponential SLA Target\n(SLA scales with entity count)', fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='upper left', fontsize=10, framealpha=0.95)
    ax.set_xlim(0.8, 700)
    ax.set_ylim(10, 2000)
    ax.grid(True, alpha=0.3, which='both')
    
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
    04 - Bullet chart with EXPONENTIAL SLA target per entity count.
    """
    # Get all entity counts for multi-row view
    all_entity_counts = set()
    for data in results.values():
        for r in data.get('latency', []):
            all_entity_counts.add(r['num_entities'])
    entity_counts = sorted(all_entity_counts)
    
    stores = list(results.keys())
    n_rows = len(stores) * len(entity_counts)
    
    fig, axes = plt.subplots(n_rows, 1, figsize=(14, 2.2 * n_rows))
    
    if n_rows == 1:
        axes = [axes]
    
    ax_idx = 0
    for store in stores:
        data = results[store]
        latency_data = data.get('latency', [])
        latency_map = {r['num_entities']: r for r in latency_data}
        color = COLORS.get(store, '#95a5a6')
        
        for entities in entity_counts:
            if ax_idx >= len(axes):
                break
            ax = axes[ax_idx]
            
            if entities not in latency_map:
                ax_idx += 1
                continue
            
            r = latency_map[entities]
            actual = r['p99']
            
            # Get exponential SLA for this entity count
            sla_target = get_sla_target(entities)
            
            # Use log scale
            ax.set_xscale('log')
            
            # Background ranges based on exponential SLA
            max_val = max(2000, actual * 1.5)
            ax.barh(0, max_val, height=0.8, color='#ffcccc', zorder=1)
            ax.barh(0, sla_target * 3, height=0.8, color='#ffffcc', zorder=2)
            ax.barh(0, sla_target, height=0.8, color='#ccffcc', zorder=3)
            
            # Actual bar
            ax.barh(0, actual, height=0.4, color=color, zorder=4, alpha=0.9)
            
            # Target marker (exponential SLA)
            ax.axvline(x=sla_target, color='black', linewidth=3, zorder=5)
            
            # Label with comparison to exponential SLA
            ratio = actual / sla_target
            label_text = f'{actual:.0f}ms'
            if ratio > 1:
                label_text += f' ({ratio:.1f}x target)'
            else:
                label_text += f' ({ratio:.0%} of target)'
            
            ax.text(actual * 1.1, 0, label_text, 
                   ha='left', va='center', fontsize=11, fontweight='bold',
                   color='green' if actual < sla_target else 'red')
            
            status = 'PASS' if actual < sla_target else 'FAIL'
            ax.set_ylabel(f'{store.upper()}\n({entities}e)\nSLA:{sla_target:.0f}ms', fontsize=10, fontweight='bold', 
                         rotation=0, ha='right', va='center')
            ax.set_xlim(10, max_val)
            ax.set_ylim(-0.5, 0.5)
            ax.set_yticks([])
            ax.set_xlabel('p99 Latency (ms) - Log Scale' if ax_idx == len(axes) - 1 else '', fontsize=11)
            
            badge_color = '#27ae60' if actual < sla_target else '#e74c3c'
            ax.text(0.98, 0.5, status, transform=ax.transAxes, ha='right', va='top',
                   fontsize=11, fontweight='bold', color='white',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor=badge_color, edgecolor='none'))
            
            ax_idx += 1
    
    legend_elements = [
        mpatches.Patch(facecolor='#ccffcc', label='Good (< SLA target)'),
        mpatches.Patch(facecolor='#ffffcc', label='Acceptable (< 3x SLA)'),
        mpatches.Patch(facecolor='#ffcccc', label='Poor (> 3x SLA)'),
        plt.Line2D([0], [0], color='black', linewidth=3, label='SLA Target (exponential)')
    ]
    fig.legend(handles=legend_elements, loc='upper right', fontsize=10, bbox_to_anchor=(0.98, 0.99))
    
    fig.suptitle('SLA Compliance with Exponential Target\n(SLA scales: 1e=20ms, 10e=41ms, 100e=153ms, 500e=407ms)', fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '04_sla_compliance.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 04_sla_compliance.png")


def chart_sla_boundary(results: Dict, output_dir: str):
    """
    05 - SLA boundary analysis with EXPONENTIAL SLA curve (not flat line).
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot each store
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if not latency_data:
            continue
        
        sorted_data = sorted(latency_data, key=lambda x: x['num_entities'])
        entities = [d['num_entities'] for d in sorted_data]
        p99_values = [d['p99'] for d in sorted_data]
        p50_values = [d.get('p50', d['p99'] * 0.8) for d in sorted_data]
        
        color = COLORS.get(store, '#95a5a6')
        
        # Fill between p50 and p99
        ax.fill_between(entities, p50_values, p99_values, alpha=0.2, color=color)
        ax.plot(entities, p99_values, color=color, linewidth=2.5, marker='o', 
               markersize=8, label=f'{store.upper()} (p99)', zorder=3)
        ax.plot(entities, p50_values, color=color, linewidth=1.5, linestyle='--',
               alpha=0.7, label=f'{store.upper()} (p50)', zorder=3)
    
    # Log scale
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    # EXPONENTIAL SLA curve (not flat!)
    x_sla = np.array([1, 2, 5, 10, 20, 50, 100, 200, 500])
    y_sla = np.array([get_sla_target(e) for e in x_sla])
    ax.plot(x_sla, y_sla, color=SLA_COLOR, linestyle='-', linewidth=4, zorder=5, 
           label='Exponential SLA Target')
    ax.fill_between(x_sla, 1, y_sla, alpha=0.15, color='green', zorder=1)
    
    # Add SLA values at key points
    for e in [1, 10, 100, 500]:
        sla = get_sla_target(e)
        ax.annotate(f'{sla:.0f}ms', xy=(e, sla), xytext=(5, -10), textcoords='offset points',
                   fontsize=10, color=SLA_COLOR, fontweight='bold')
    
    # Add zone labels
    ax.annotate('SLA COMPLIANT\n(under curve)', xy=(3, 12), fontsize=11, fontweight='bold',
               color='darkgreen', ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
    ax.annotate('SLA VIOLATION\n(above curve)', xy=(200, 800), fontsize=11, fontweight='bold',
               color='darkred', ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
    
    ax.set_xlabel('Entity Count (Log Scale)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Latency (ms) - Log Scale', fontsize=13, fontweight='bold')
    ax.set_title('SLA Boundary Analysis - Exponential Target\nSLA(n) = 20ms × (1 + log₂(n) × √n / 10)', fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='upper left', fontsize=9, ncol=2, framealpha=0.95)
    ax.set_xlim(0.8, 700)
    ax.set_ylim(10, 2000)
    ax.grid(True, alpha=0.3, which='both')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '05_sla_boundary.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 05_sla_boundary.png")


def chart_statefarm_sla(results: Dict, output_dir: str):
    """
    06 - State Farm SLA visualization: 50/200 entities, 200 features, 60ms target.
    """
    fig, ax = plt.subplots(figsize=(14, 9))
    
    # Plot each store with interpolation for 50 and 200 entities
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if not latency_data:
            continue
        
        sorted_data = sorted(latency_data, key=lambda x: x['num_entities'])
        entities = [d['num_entities'] for d in sorted_data]
        p99_values = [d['p99'] for d in sorted_data]
        
        color = COLORS.get(store, '#95a5a6')
        
        # Plot the line
        ax.plot(entities, p99_values, color=color, linewidth=3, marker='o', 
               markersize=10, label=f'{store.upper()}', zorder=3)
        
        # Interpolate for State Farm's entity counts (50, 200)
        import numpy as np
        for sf_entities in STATEFARM_ENTITIES:
            if sf_entities in entities:
                idx = entities.index(sf_entities)
                estimated = p99_values[idx]
            else:
                # Linear interpolation on log scale
                log_entities = np.log10(entities)
                log_p99 = np.log10(p99_values)
                estimated = 10 ** np.interp(np.log10(sf_entities), log_entities, log_p99)
            
            # Mark the State Farm points
            ax.scatter([sf_entities], [estimated], s=200, color=color, 
                      marker='*', edgecolors='black', linewidths=1.5, zorder=5)
            ax.annotate(f'{estimated:.0f}ms', xy=(sf_entities, estimated),
                       xytext=(10, 10), textcoords='offset points',
                       fontsize=10, fontweight='bold', color=color)
    
    # Log scale
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    # STATE FARM's flat 60ms SLA line
    ax.axhline(y=STATEFARM_SLA_MS, color=STATEFARM_COLOR, linestyle='-', linewidth=4, 
              zorder=4, label=f'State Farm SLA ({STATEFARM_SLA_MS}ms)')
    ax.fill_between([0.5, 1000], 1, STATEFARM_SLA_MS, alpha=0.15, color=STATEFARM_COLOR, zorder=1)
    
    # State Farm's entity count markers (50, 200)
    for sf_e in STATEFARM_ENTITIES:
        ax.axvline(x=sf_e, color=STATEFARM_COLOR, linestyle=':', linewidth=2.5, alpha=0.8, zorder=2)
        ax.annotate(f'State Farm\n{sf_e} entities', xy=(sf_e, 15), fontsize=10, 
                   color=STATEFARM_COLOR, fontweight='bold', ha='center', va='bottom',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor=STATEFARM_COLOR))
    
    # Add State Farm requirement box
    ax.annotate(
        'STATE FARM REQUIREMENTS\n'
        f'• Entities: {STATEFARM_ENTITIES[0]}, {STATEFARM_ENTITIES[1]}\n'
        f'• Features: {STATEFARM_FEATURES}\n'
        f'• SLA: {STATEFARM_SLA_MS}ms p99\n'
        '• Throughput: 3M/hour',
        xy=(0.02, 0.98), xycoords='axes fraction',
        fontsize=11, fontweight='bold', color=STATEFARM_COLOR,
        va='top', ha='left',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.95, edgecolor=STATEFARM_COLOR, linewidth=2)
    )
    
    # Add compliance status for each store at 50 and 200 entities
    y_pos = 0.75
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if not latency_data:
            continue
        sorted_data = sorted(latency_data, key=lambda x: x['num_entities'])
        entities = [d['num_entities'] for d in sorted_data]
        p99_values = [d['p99'] for d in sorted_data]
        
        # Estimate at 50 and 200
        status_text = f'{store.upper()}: '
        for sf_e in STATEFARM_ENTITIES:
            log_entities = np.log10(entities)
            log_p99 = np.log10(p99_values)
            est = 10 ** np.interp(np.log10(sf_e), log_entities, log_p99)
            status = '✓' if est < STATEFARM_SLA_MS else '✗'
            status_text += f'{sf_e}e={est:.0f}ms{status}  '
        
        color = COLORS.get(store, '#95a5a6')
        ax.annotate(status_text, xy=(0.98, y_pos), xycoords='axes fraction',
                   fontsize=10, fontweight='bold', color=color, ha='right',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
        y_pos -= 0.06
    
    ax.set_xlabel('Entity Count (Log Scale)', fontsize=13, fontweight='bold')
    ax.set_ylabel('p99 Latency (ms) - Log Scale', fontsize=13, fontweight='bold')
    ax.set_title('State Farm SLA Analysis\n50 & 200 Entities @ 60ms Target (200 Features)', 
                fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='lower right', fontsize=10, framealpha=0.95)
    ax.set_xlim(0.8, 700)
    ax.set_ylim(10, 2000)
    ax.grid(True, alpha=0.3, which='both')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '06_statefarm_sla.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 06_statefarm_sla.png")


def main():
    parser = argparse.ArgumentParser(
        description="Generate curated benchmark charts (5 charts with log scale)",
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
    print("CHART GENERATOR (Log Scale Edition)")
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
    chart_sla_boundary(results, args.output)
    chart_statefarm_sla(results, args.output)
    
    print("-" * 60)
    print("Done! 6 charts generated (with log scale + State Farm SLA).")
    print("=" * 60)


if __name__ == "__main__":
    main()
