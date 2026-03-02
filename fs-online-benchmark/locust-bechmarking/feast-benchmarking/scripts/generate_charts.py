#!/usr/bin/env python3
"""
Feast Benchmark Chart Generator - Creates visualization charts.

Benchmark Charts (from latency results):
  01_latency_by_entities.png   - P99 latency grouped by entity count (entity_scaling)
  01b_latency_by_features.png  - P99 latency grouped by feature count (feature_scaling)
  06_executive_summary.png     - Key metrics at a glance (4-panel)
  07_production_sla.png        - Production SLA analysis (50 & 200 entities)

Bottleneck Analysis Charts (from profiling data if available):
  09_bottleneck_breakdown.png  - Top functions by time per store
  10_category_comparison.png   - Time by category across stores

Cross-Reference Comparison (when using --compare-refs):
  01_cross_reference_comparison.png - v0.60.0 vs Master vs Optimized
"""
import argparse
import json
import os
from typing import Dict, List

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.style.use('seaborn-v0_8-whitegrid')

COLORS = {
    'sqlite': '#2ecc71',    # Green
    'redis': '#e74c3c',     # Red  
    'dynamodb': '#f39c12',  # Orange
    'postgres': '#3498db',  # Blue
}

# Production SLA requirement
SLA_TARGET_MS = 60


def load_results(result_dirs: List[str], names: List[str], scenario: str = None) -> Dict[str, Dict]:
    """
    Load benchmark results from directories.
    
    Supports both old structure (store/benchmark_results.json) and new structure 
    (store/{scenario}/benchmark_results.json).
    
    Args:
        result_dirs: List of directory paths (e.g., [results/master/sqlite, results/master/redis])
        names: List of store names (e.g., [sqlite, redis])
        scenario: If specified, load only this scenario (entity_scaling or feature_scaling)
    """
    results = {}
    for dir_path, name in zip(result_dirs, names):
        # Try new structure first: store/{scenario}/benchmark_results.json
        scenarios_to_try = [scenario] if scenario else ['entity_scaling', 'feature_scaling']
        
        for sc in scenarios_to_try:
            json_path = os.path.join(dir_path, sc, "benchmark_results.json")
            if os.path.exists(json_path):
                with open(json_path) as f:
                    data = json.load(f)
                    if name not in results:
                        results[name] = data
                    else:
                        # Merge latency data from multiple scenarios
                        results[name].setdefault('latency', []).extend(data.get('latency', []))
                continue
        
        # Fallback to old structure: store/benchmark_results.json
        json_path = os.path.join(dir_path, "benchmark_results.json")
        if os.path.exists(json_path) and name not in results:
            with open(json_path) as f:
                results[name] = json.load(f)
    
    return results


def load_scenario_results(result_dirs: List[str], names: List[str], scenario: str) -> Dict[str, Dict]:
    """Load benchmark results for a specific scenario only."""
    results = {}
    for dir_path, name in zip(result_dirs, names):
        json_path = os.path.join(dir_path, scenario, "benchmark_results.json")
        if os.path.exists(json_path):
            with open(json_path) as f:
                results[name] = json.load(f)
    return results


def chart_01_latency_by_entities(results: Dict, output_dir: str):
    """
    01 - Grouped bar chart: P99 latency by entity count for each store.
    Clear comparison of stores at each scale point.
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Get all entity counts
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
                     edgecolor='white', linewidth=1)
        
        # Add value labels
        for bar, val in zip(bars, values):
            if val > 0:
                ax.annotate(f'{val:.0f}',
                           xy=(bar.get_x() + bar.get_width()/2, val),
                           xytext=(0, 3), textcoords='offset points',
                           ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    # 60ms reference line
    ax.axhline(y=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2, 
               label=f'Target: {SLA_TARGET_MS}ms', zorder=5)
    
    ax.set_xlabel('Entity Count', fontsize=12, fontweight='bold')
    ax.set_ylabel('P99 Latency (ms)', fontsize=12, fontweight='bold')
    ax.set_title('P99 Latency by Entity Count\n200 Features, 100 Iterations', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(entities)))
    ax.set_xticklabels([str(e) for e in entities])
    ax.legend(loc='upper left', fontsize=10)
    ax.set_ylim(0, None)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '01_latency_by_entities.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 01_latency_by_entities.png")


def chart_01b_latency_by_features(results: Dict, output_dir: str):
    """
    01b - Grouped bar chart: P99 latency by feature count for each store.
    Parallel to chart_01 but with features on X-axis instead of entities.
    Used for feature_scaling scenario results.
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Get all feature counts from results
    all_features = set()
    for data in results.values():
        for r in data.get('latency', []):
            all_features.add(r.get('num_features', 200))
    features = sorted(all_features)
    
    # Skip if only one feature count (entity_scaling scenario)
    if len(features) <= 1:
        plt.close()
        print("Skipped: 01b_latency_by_features.png (single feature count - use entity_scaling results)")
        return
    
    stores = list(results.keys())
    n_stores = len(stores)
    bar_width = 0.8 / n_stores
    
    for i, store in enumerate(stores):
        data = results[store]
        # Map by num_features instead of num_entities
        latency_map = {r.get('num_features', 200): r['p99'] for r in data.get('latency', [])}
        
        x_pos = np.arange(len(features)) + i * bar_width - (n_stores - 1) * bar_width / 2
        values = [latency_map.get(f, 0) for f in features]
        
        bars = ax.bar(x_pos, values, bar_width * 0.9,
                     label=store.upper(),
                     color=COLORS.get(store, '#95a5a6'),
                     edgecolor='white', linewidth=1)
        
        # Add value labels
        for bar, val in zip(bars, values):
            if val > 0:
                ax.annotate(f'{val:.0f}',
                           xy=(bar.get_x() + bar.get_width()/2, val),
                           xytext=(0, 3), textcoords='offset points',
                           ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    # 60ms reference line
    ax.axhline(y=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2, 
               label=f'Target: {SLA_TARGET_MS}ms', zorder=5)
    
    ax.set_xlabel('Feature Count', fontsize=12, fontweight='bold')
    ax.set_ylabel('P99 Latency (ms)', fontsize=12, fontweight='bold')
    ax.set_title('P99 Latency by Feature Count\n50 Entities (Fixed), 100 Iterations', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(features)))
    ax.set_xticklabels([str(f) for f in features])
    ax.legend(loc='upper left', fontsize=10)
    ax.set_ylim(0, None)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '01b_latency_by_features.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 01b_latency_by_features.png")


def chart_02_scaling_curves(results: Dict, output_dir: str):
    """
    02 - Line chart showing how latency scales with entity count.
    Log-log scale to see scaling characteristics clearly.
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
        
        ax.plot(entities, latencies, color=color, linewidth=3, marker='o', 
               markersize=10, markerfacecolor='white', markeredgewidth=2.5, 
               label=store.upper(), zorder=3)
        
        # Label endpoints
        ax.annotate(f'{latencies[0]:.0f}ms', xy=(entities[0], latencies[0]),
                   xytext=(-15, 5), textcoords='offset points',
                   fontsize=9, fontweight='bold', color=color)
        ax.annotate(f'{latencies[-1]:.0f}ms', xy=(entities[-1], latencies[-1]),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=9, fontweight='bold', color=color)
    
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    # 60ms reference
    ax.axhline(y=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=3, 
               label=f'Target: {SLA_TARGET_MS}ms', zorder=4)
    
    # Ideal linear scaling reference (from 1 entity baseline)
    x_ref = np.array([1, 10, 100, 500])
    y_ref = 15 * x_ref  # Linear scaling from ~15ms at 1 entity
    ax.plot(x_ref, y_ref, color='gray', linestyle=':', linewidth=2, alpha=0.5,
           label='Linear Scaling (ref)')
    
    ax.set_xlabel('Entity Count (log scale)', fontsize=12, fontweight='bold')
    ax.set_ylabel('P99 Latency in ms (log scale)', fontsize=12, fontweight='bold')
    ax.set_title('Latency Scaling Behavior\nHow latency grows with entity count', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10)
    ax.set_xlim(0.8, 700)
    ax.set_ylim(10, 2500)
    ax.grid(True, alpha=0.3, which='both')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '02_scaling_curves.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 02_scaling_curves.png")


def chart_03_store_ranking(results: Dict, output_dir: str):
    """
    03 - Horizontal bar chart ranking stores by performance at key entity counts.
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 6))
    
    key_entities = [1, 100, 500]
    
    for ax, target_entities in zip(axes, key_entities):
        store_latencies = []
        
        for store, data in results.items():
            latency_data = data.get('latency', [])
            for r in latency_data:
                if r['num_entities'] == target_entities:
                    store_latencies.append((store, r['p99']))
                    break
        
        # Sort by latency (fastest first)
        store_latencies.sort(key=lambda x: x[1])
        
        stores = [s[0] for s in store_latencies]
        latencies = [s[1] for s in store_latencies]
        colors = [COLORS.get(s, '#95a5a6') for s in stores]
        
        y_pos = np.arange(len(stores))
        bars = ax.barh(y_pos, latencies, color=colors, edgecolor='white', height=0.6)
        
        # Add value labels
        for bar, lat in zip(bars, latencies):
            label = f'{lat:.0f}ms'
            if lat > SLA_TARGET_MS:
                label += f' ({lat/SLA_TARGET_MS:.1f}x)'
            ax.text(lat + 10, bar.get_y() + bar.get_height()/2, label,
                   va='center', fontsize=10, fontweight='bold')
        
        # 60ms reference
        ax.axvline(x=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2)
        ax.text(SLA_TARGET_MS, len(stores) - 0.3, f'{SLA_TARGET_MS}ms', 
               color='#c0392b', fontsize=9, fontweight='bold', va='top')
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels([s.upper() for s in stores])
        ax.set_xlabel('P99 Latency (ms)')
        ax.set_title(f'{target_entities} Entities', fontsize=12, fontweight='bold')
        ax.set_xlim(0, max(latencies) * 1.3 if latencies else 100)
        ax.grid(axis='x', alpha=0.3)
    
    fig.suptitle('Store Performance Ranking\n(Fastest to Slowest)', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '03_store_ranking.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 03_store_ranking.png")


def chart_04_time_breakdown(results: Dict, output_dir: str, profile_data: Dict = None):
    """
    04 - Stacked bar showing where time is spent at 50 entities (production target).
    Uses profile data for accurate breakdown when available.
    """
    fig, ax = plt.subplots(figsize=(12, 7))
    
    breakdown_data = []
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if not latency_data:
            continue
        
        # Find 50 entity result (production target) or closest
        r = None
        for lat in sorted(latency_data, key=lambda x: abs(x['num_entities'] - 50)):
            r = lat
            break
        
        if not r:
            continue
        
        total = r['p99']
        entities = r['num_entities']
        
        # Use profile data for accurate breakdown if available
        if profile_data and store in profile_data and 'breakdown' in profile_data[store]:
            bd = profile_data[store]['breakdown']
            online_read_pct = bd.get('DB/Store Read', {}).get('pct', 10)
            protobuf_pct = bd.get('Protobuf/Serialization', {}).get('pct', 15)
            timestamp_pct = bd.get('Timestamp Handling', {}).get('pct', 8)
            typecheck_pct = bd.get('Type Checking', {}).get('pct', 7)
            other_pct = bd.get('Other', {}).get('pct', 60)
        else:
            # Fallback estimates
            online_read_pct = 15
            protobuf_pct = 20
            timestamp_pct = 10
            typecheck_pct = 8
            other_pct = 47
        
        breakdown_data.append({
            'store': store,
            'entities': entities,
            'total': total,
            'online_read': total * online_read_pct / 100,
            'protobuf': total * protobuf_pct / 100,
            'timestamp': total * timestamp_pct / 100,
            'typecheck': total * typecheck_pct / 100,
            'other': total * other_pct / 100
        })
    
    # Sort by total (fastest first)
    if not breakdown_data:
        print("Skipped: 04_time_breakdown.png (no data)")
        return
    
    breakdown_data.sort(key=lambda x: x['total'])
    
    stores = [d['store'].upper() for d in breakdown_data]
    y_pos = np.arange(len(stores))
    
    online_read = [d['online_read'] for d in breakdown_data]
    protobuf = [d['protobuf'] for d in breakdown_data]
    timestamp = [d['timestamp'] for d in breakdown_data]
    typecheck = [d['typecheck'] for d in breakdown_data]
    other = [d['other'] for d in breakdown_data]
    
    # Stacked horizontal bars with 5 categories
    ax.barh(y_pos, online_read, height=0.6, label='DB/Store Read', color='#3498db')
    left1 = online_read
    ax.barh(y_pos, protobuf, height=0.6, left=left1, label='Protobuf/Serialization', color='#e74c3c')
    left2 = [a+b for a,b in zip(left1, protobuf)]
    ax.barh(y_pos, timestamp, height=0.6, left=left2, label='Timestamp Handling', color='#f39c12')
    left3 = [a+b for a,b in zip(left2, timestamp)]
    ax.barh(y_pos, typecheck, height=0.6, left=left3, label='Type Checking', color='#9b59b6')
    left4 = [a+b for a,b in zip(left3, typecheck)]
    ax.barh(y_pos, other, height=0.6, left=left4, label='Other', color='#95a5a6')
    
    # Total labels with SLA status
    for i, d in enumerate(breakdown_data):
        status = "[PASS]" if d['total'] < SLA_TARGET_MS else "[FAIL]"
        ax.text(d['total'] + 10, i, f"{d['total']:.0f}ms {status}",
               va='center', fontsize=10, fontweight='bold',
               color='#27ae60' if d['total'] < SLA_TARGET_MS else '#c0392b')
    
    # 60ms reference
    ax.axvline(x=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2.5)
    ax.text(SLA_TARGET_MS + 2, len(stores) - 0.5, f'{SLA_TARGET_MS}ms SLA', 
           color='#c0392b', fontsize=9, fontweight='bold', va='top')
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stores)
    ax.set_xlabel('Time (ms)', fontsize=12, fontweight='bold')
    
    entities_shown = breakdown_data[0]["entities"] if breakdown_data else 50
    data_source = "from profiling" if profile_data else "estimated"
    ax.set_title(f'Time Breakdown at {entities_shown} Entities × 200 Features ({data_source})\nWhere is latency spent?', 
                fontsize=14, fontweight='bold')
    ax.legend(loc='lower right', fontsize=9, ncol=2)
    ax.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '04_time_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 04_time_breakdown.png")


def chart_05_sla_gap_analysis(results: Dict, output_dir: str):
    """
    05 - Show the gap between actual performance and 60ms target.
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Get max entity count data
    gap_data = []
    for store, data in results.items():
        latency_data = data.get('latency', [])
        for r in sorted(latency_data, key=lambda x: x['num_entities']):
            gap_data.append({
                'store': store,
                'entities': r['num_entities'],
                'p99': r['p99'],
                'gap': r['p99'] - SLA_TARGET_MS,
                'multiplier': r['p99'] / SLA_TARGET_MS
            })
    
    # Group by entity count
    all_entities = sorted(set(d['entities'] for d in gap_data))
    stores = list(results.keys())
    
    x = np.arange(len(all_entities))
    width = 0.8 / len(stores)
    
    for i, store in enumerate(stores):
        store_data = [d for d in gap_data if d['store'] == store]
        multipliers = []
        for ent in all_entities:
            match = [d for d in store_data if d['entities'] == ent]
            multipliers.append(match[0]['multiplier'] if match else 0)
        
        offset = (i - len(stores)/2 + 0.5) * width
        bars = ax.bar(x + offset, multipliers, width * 0.9, 
                     label=store.upper(), color=COLORS.get(store, '#95a5a6'))
        
        # Add labels
        for bar, mult in zip(bars, multipliers):
            if mult > 0:
                ax.annotate(f'{mult:.1f}x',
                           xy=(bar.get_x() + bar.get_width()/2, mult),
                           xytext=(0, 3), textcoords='offset points',
                           ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    # SLA line at 1x
    ax.axhline(y=1.0, color='#27ae60', linestyle='-', linewidth=3, label='Meeting SLA (1x)')
    ax.fill_between([-0.5, len(all_entities)], 0, 1, alpha=0.1, color='green')
    
    ax.set_xlabel('Entity Count', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'Multiplier vs {SLA_TARGET_MS}ms Target', fontsize=12, fontweight='bold')
    ax.set_title(f'SLA Gap Analysis\nHow many times over the {SLA_TARGET_MS}ms target?', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([str(e) for e in all_entities])
    ax.legend(loc='upper left', fontsize=10)
    ax.set_ylim(0, None)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '05_sla_gap_analysis.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 05_sla_gap_analysis.png")


def chart_06_executive_summary(results: Dict, output_dir: str):
    """
    06 - Executive summary with key metrics.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # --- Top Left: Best store at each entity count ---
    ax = axes[0, 0]
    all_entities = set()
    for data in results.values():
        for r in data.get('latency', []):
            all_entities.add(r['num_entities'])
    entities = sorted(all_entities)
    
    best_stores = []
    best_latencies = []
    for ent in entities:
        best = None
        best_lat = float('inf')
        for store, data in results.items():
            for r in data.get('latency', []):
                if r['num_entities'] == ent and r['p99'] < best_lat:
                    best = store
                    best_lat = r['p99']
        best_stores.append(best)
        best_latencies.append(best_lat)
    
    colors = [COLORS.get(s, '#95a5a6') for s in best_stores]
    bars = ax.bar(range(len(entities)), best_latencies, color=colors, edgecolor='white')
    
    for i, (bar, store, lat) in enumerate(zip(bars, best_stores, best_latencies)):
        ax.text(bar.get_x() + bar.get_width()/2, lat + 20, 
               f'{store.upper()}\n{lat:.0f}ms', ha='center', fontsize=9, fontweight='bold')
    
    ax.axhline(y=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2)
    ax.set_xticks(range(len(entities)))
    ax.set_xticklabels([str(e) for e in entities])
    ax.set_xlabel('Entity Count')
    ax.set_ylabel('Best P99 Latency (ms)')
    ax.set_title('Best Store per Entity Count', fontweight='bold')
    
    # --- Top Right: SLA Pass Rate ---
    ax = axes[0, 1]
    pass_data = []
    for store, data in results.items():
        latency_data = data.get('latency', [])
        total = len(latency_data)
        passed = sum(1 for r in latency_data if r['p99'] < SLA_TARGET_MS)
        pass_data.append({'store': store, 'passed': passed, 'total': total, 
                         'rate': passed/total*100 if total > 0 else 0})
    
    pass_data.sort(key=lambda x: x['rate'], reverse=True)
    stores = [d['store'].upper() for d in pass_data]
    rates = [d['rate'] for d in pass_data]
    colors = [COLORS.get(d['store'], '#95a5a6') for d in pass_data]
    
    bars = ax.barh(range(len(stores)), rates, color=colors, edgecolor='white', height=0.6)
    for i, (bar, d) in enumerate(zip(bars, pass_data)):
        ax.text(bar.get_width() + 2, i, f"{d['passed']}/{d['total']} ({d['rate']:.0f}%)",
               va='center', fontsize=10, fontweight='bold')
    
    ax.set_yticks(range(len(stores)))
    ax.set_yticklabels(stores)
    ax.set_xlabel(f'% Tests Under {SLA_TARGET_MS}ms')
    ax.set_title('SLA Pass Rate', fontweight='bold')
    ax.set_xlim(0, 110)
    
    # --- Bottom Left: Latency at 50 entities (Production Target) ---
    ax = axes[1, 0]
    lat_50 = []
    for store, data in results.items():
        for r in data.get('latency', []):
            if r['num_entities'] == 50:
                lat_50.append({'store': store, 'p99': r['p99'], 'mean': r.get('mean', r['p99'])})
    
    lat_50.sort(key=lambda x: x['p99'])
    stores = [d['store'].upper() for d in lat_50]
    latencies = [d['p99'] for d in lat_50]
    colors = [COLORS.get(d['store'], '#95a5a6') for d in lat_50]
    
    bars = ax.barh(range(len(stores)), latencies, color=colors, edgecolor='white', height=0.6)
    for i, (bar, lat) in enumerate(zip(bars, latencies)):
        status = "PASS" if lat < SLA_TARGET_MS else f"{lat/SLA_TARGET_MS:.1f}x"
        color = '#27ae60' if lat < SLA_TARGET_MS else '#c0392b'
        ax.text(lat + 5, i, f'{lat:.0f}ms ({status})',
               va='center', fontsize=10, fontweight='bold', color=color)
    
    ax.axvline(x=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2, label=f'{SLA_TARGET_MS}ms SLA')
    ax.set_yticks(range(len(stores)))
    ax.set_yticklabels(stores)
    ax.set_xlabel('P99 Latency (ms)')
    ax.set_title('Performance at 50 Entities × 200 Features (Production Target)', fontweight='bold')
    ax.legend(loc='lower right')
    
    # --- Bottom Right: Key Findings ---
    ax = axes[1, 1]
    ax.axis('off')
    
    # Calculate key stats
    best_store_50 = lat_50[0]['store'] if lat_50 else 'N/A'
    best_lat_50 = lat_50[0]['p99'] if lat_50 else 0
    worst_lat_50 = lat_50[-1]['p99'] if lat_50 else 0
    passes_sla = best_lat_50 < SLA_TARGET_MS if lat_50 else False
    
    # Also get 200 entity results for comparison
    lat_200 = []
    for store, data in results.items():
        for r in data.get('latency', []):
            if r['num_entities'] == 200:
                lat_200.append({'store': store, 'p99': r['p99']})
    lat_200.sort(key=lambda x: x['p99'])
    best_lat_200 = lat_200[0]['p99'] if lat_200 else 0
    
    sla_status = "PASS" if passes_sla else "FAIL"
    gap_text = "within target" if passes_sla else f"{best_lat_50/SLA_TARGET_MS:.1f}x over target"
    
    findings = f"""
KEY FINDINGS

Target: {SLA_TARGET_MS}ms p99 latency
Config: 50 entities × 200 features

RESULTS AT 50 ENTITIES:
• Best Store: {best_store_50.upper()} ({best_lat_50:.0f}ms)
• Status: {sla_status} - {gap_text}
• Range: {best_lat_50:.0f}ms - {worst_lat_50:.0f}ms

RESULTS AT 200 ENTITIES:
• Best: {lat_200[0]['store'].upper() if lat_200 else 'N/A'} ({best_lat_200:.0f}ms)
• Status: {'PASS' if best_lat_200 < SLA_TARGET_MS else 'FAIL'}

RANKING @ 50 ENTITIES:
{chr(10).join(f"  {i+1}. {d['store'].upper()}: {d['p99']:.0f}ms" for i, d in enumerate(lat_50))}

CONCLUSION:
{'SLA achievable at 50 entities.' if passes_sla else 'Code-level optimizations required.'}
"""
    
    ax.text(0.05, 0.95, findings, transform=ax.transAxes, fontsize=11,
           verticalalignment='top', fontfamily='monospace',
           bbox=dict(boxstyle='round', facecolor='#f8f9fa', edgecolor='#dee2e6'))
    
    fig.suptitle('Feast Online Store Benchmark - Executive Summary', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '03_executive_summary.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 03_executive_summary.png")


def chart_07_production_sla(results: Dict, output_dir: str):
    """
    07 - Production SLA Analysis with log-log scale, 60ms target line,
    and annotations at key entity counts (50, 200).
    """
    fig, ax = plt.subplots(figsize=(14, 9))
    
    # Production requirements box
    req_text = "PRODUCTION REQUIREMENTS\n• Entities: 50, 200\n• Features: 200\n• SLA: 60ms p99\n• Throughput: 3M/hour"
    ax.text(0.02, 0.98, req_text, transform=ax.transAxes, fontsize=10,
           verticalalignment='top', fontfamily='monospace',
           bbox=dict(boxstyle='round', facecolor='#ffffcc', edgecolor='#ff9800', linewidth=2))
    
    # Plot each store
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if len(latency_data) < 2:
            continue
        
        sorted_data = sorted(latency_data, key=lambda x: x['num_entities'])
        entities = [d['num_entities'] for d in sorted_data]
        latencies = [d['p99'] for d in sorted_data]
        color = COLORS.get(store, '#95a5a6')
        
        ax.plot(entities, latencies, color=color, linewidth=2.5, marker='o', 
               markersize=8, markerfacecolor='white', markeredgewidth=2, 
               label=store.upper(), zorder=3)
        
        # Annotate key points (50 and 200 entities)
        for target_ent in [50, 200]:
            for d in sorted_data:
                if d['num_entities'] == target_ent:
                    lat = d['p99']
                    # Star marker for key points
                    ax.plot(target_ent, lat, marker='*', markersize=15, 
                           color=color, markeredgecolor='black', markeredgewidth=0.5, zorder=5)
                    break
        
        # Add endpoint labels
        lat_50 = next((d['p99'] for d in sorted_data if d['num_entities'] == 50), None)
        lat_200 = next((d['p99'] for d in sorted_data if d['num_entities'] == 200), None)
        if lat_50 and lat_200:
            ax.annotate(f'{store.upper()}: 50e={lat_50:.0f}ms  200e={lat_200:.0f}ms',
                       xy=(200, lat_200), xytext=(250, lat_200),
                       fontsize=8, color=color, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    # 60ms SLA line (purple, prominent)
    ax.axhline(y=SLA_TARGET_MS, color='#9b59b6', linestyle='-', linewidth=3, 
               label=f'Target SLA ({SLA_TARGET_MS}ms)', zorder=4)
    ax.fill_between([0.5, 1000], 0, SLA_TARGET_MS, alpha=0.1, color='#9b59b6')
    
    # Vertical lines at target entity counts
    for target_ent in [50, 200]:
        ax.axvline(x=target_ent, color='gray', linestyle=':', linewidth=1.5, alpha=0.7)
        ax.text(target_ent, 8, f'Target\n{target_ent} entities', 
               ha='center', fontsize=8, color='gray')
    
    ax.set_xlabel('Entity Count (Log Scale)', fontsize=12, fontweight='bold')
    ax.set_ylabel('p99 Latency (ms) - Log Scale', fontsize=12, fontweight='bold')
    ax.set_title('Production SLA Analysis\n50 & 200 Entities @ 60ms Target (200 Features)', 
                fontsize=14, fontweight='bold', color='#9b59b6')
    ax.legend(loc='lower right', fontsize=10)
    ax.set_xlim(0.8, 700)
    ax.set_ylim(10, 2000)
    ax.grid(True, alpha=0.3, which='both')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '02_production_sla.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 02_production_sla.png")


def chart_08_time_distribution(results: Dict, output_dir: str, profile_data: Dict = None):
    """
    08 - Donut charts showing time distribution by component for each store.
    Uses profile data (bottleneck_analysis.json) when available for accurate breakdown.
    """
    COMPONENT_COLORS = {
        'DB/Store Read': '#3498db',
        'Protobuf/Serialization': '#e74c3c',
        'Timestamp Handling': '#f39c12',
        'Type Checking': '#9b59b6',
        'Entity Processing': '#1abc9c',
        'Other': '#95a5a6',
    }
    
    n_stores = len(results)
    cols = min(2, n_stores)
    rows = (n_stores + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 5 * rows), squeeze=False)
    axes = axes.flatten()
    
    target_entities = 50  # Production target
    
    for idx, (store, data) in enumerate(results.items()):
        ax = axes[idx]
        
        # Get latency at target entity count (50 for production)
        latency_data = data.get('latency', [])
        total_ms = 0
        entities_used = target_entities
        
        # Find closest entity count to target
        for r in sorted(latency_data, key=lambda x: abs(x['num_entities'] - target_entities)):
            total_ms = r['p99']
            entities_used = r['num_entities']
            break
        
        # Use profile data breakdown if available (much more accurate)
        breakdown = {}
        if profile_data and store in profile_data and 'breakdown' in profile_data[store]:
            prof_breakdown = profile_data[store]['breakdown']
            for cat, cat_data in prof_breakdown.items():
                pct = cat_data.get('pct', 0)
                if pct > 1:  # Only include if > 1%
                    breakdown[cat] = pct
        
        # Fallback if no profile data
        if not breakdown:
            breakdown = {
                'DB/Store Read': 25,
                'Protobuf/Serialization': 40,
                'Timestamp Handling': 10,
                'Type Checking': 10,
                'Other': 15,
            }
        
        # Create donut chart
        sizes = list(breakdown.values())
        labels = list(breakdown.keys())
        colors = [COMPONENT_COLORS.get(l, '#95a5a6') for l in labels]
        
        wedges, texts, autotexts = ax.pie(sizes, labels=None, colors=colors, autopct='%1.0f%%',
                                          startangle=90, pctdistance=0.75,
                                          wedgeprops=dict(width=0.5, edgecolor='white'))
        
        # Style the percentage labels
        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_fontweight('bold')
        
        # Center text with actual latency at target entities
        ax.text(0, 0, f'{store.upper()}\n{entities_used}e: {total_ms:.0f}ms', ha='center', va='center',
               fontsize=11, fontweight='bold')
        
        ax.set_title(f'{store.upper()}', fontsize=12, fontweight='bold', pad=10)
    
    # Hide unused axes
    for idx in range(len(results), len(axes)):
        axes[idx].axis('off')
    
    # Add legend
    legend_patches = [mpatches.Patch(color=COMPONENT_COLORS[c], label=c) for c in COMPONENT_COLORS]
    fig.legend(handles=legend_patches, loc='center right', fontsize=10, bbox_to_anchor=(1.15, 0.5))
    
    data_source = "from benchmark profiling" if profile_data else "estimated"
    fig.suptitle(f'Time Distribution by Component ({data_source})\n({target_entities} entities, 200 features)', 
                fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '08_time_distribution.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 08_time_distribution.png")


def chart_09_bottleneck_breakdown(profile_data: Dict, output_dir: str, benchmark_stores: List[str] = None):
    """
    09 - Horizontal bar chart showing top functions by time across all stores.
    Includes total latency summary and config details like chart 07.
    Only shows stores that were actually benchmarked.
    Shows more functions (20) with full names for detailed analysis.
    """
    fig, axes = plt.subplots(2, 2, figsize=(22, 18))
    axes = axes.flatten()
    
    # Filter to only benchmarked stores
    all_stores = list(profile_data.keys())
    if benchmark_stores:
        stores = [s for s in all_stores if s in benchmark_stores][:4]
    else:
        stores = all_stores[:4]
    store_colors = {'sqlite': '#3498db', 'redis': '#e74c3c', 'postgres': '#2ecc71', 'dynamodb': '#9b59b6'}
    bar_colors = ['#3498db', '#e74c3c', '#2ecc71', '#9b59b6', '#f39c12', '#1abc9c', '#34495e', '#e67e22', 
                  '#16a085', '#8e44ad', '#2c3e50', '#c0392b', '#27ae60', '#d35400', '#7f8c8d', '#2980b9',
                  '#c0392b', '#1abc9c', '#9b59b6', '#f1c40f']
    
    # Get config from first valid store
    config_entities = 50
    config_features = 200
    for store in stores:
        if 'entities' in profile_data.get(store, {}):
            config_entities = profile_data[store]['entities']
            config_features = profile_data[store]['features']
            break
    
    for idx, store in enumerate(stores):
        ax = axes[idx]
        data = profile_data.get(store, {})
        
        if 'error' in data or 'top_functions' not in data:
            ax.text(0.5, 0.5, f'{store.upper()}\nNo data', ha='center', va='center', fontsize=14)
            ax.axis('off')
            continue
        
        # Get latency info
        latency = data.get('latency', {})
        avg_ms = latency.get('avg_ms', 0)
        p50_ms = latency.get('p50_ms', 0)
        p99_ms = latency.get('p99_ms', 0)
        
        # Show more functions (20) with fuller names (50 chars)
        top_funcs = data['top_functions'][:20]
        names = [f['name'][:50] for f in top_funcs]
        times = [f['total_ms'] for f in top_funcs]
        calls = [f.get('calls', 0) for f in top_funcs]
        
        # Calculate percentages
        pcts = [(t / avg_ms * 100) if avg_ms > 0 else 0 for t in times]
        
        bars = ax.barh(range(len(names)), times, color=bar_colors[:len(names)], edgecolor='white', linewidth=0.5)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=7, fontfamily='monospace')
        ax.invert_yaxis()
        ax.set_xlabel('Time (ms)', fontsize=10, fontweight='bold')
        
        # Add time and percentage labels
        max_time = max(times) if times else 1
        for bar, t, pct, c in zip(bars, times, pcts, calls):
            label = f'{t:.1f}ms ({pct:.0f}%)'
            if c > 50:
                label += f' [{c:.0f}x]'
            ax.text(bar.get_width() + max_time * 0.02, bar.get_y() + bar.get_height()/2, 
                   label, va='center', fontsize=6, fontweight='bold')
        
        # Store title with latency summary
        sla_status = "[PASS]" if p99_ms < 60 else "[FAIL]"
        title_color = store_colors.get(store, '#333333')
        ax.set_title(f'{store.upper()} - Total: {avg_ms:.0f}ms (p99: {p99_ms:.0f}ms) {sla_status}', 
                    fontsize=12, fontweight='bold', color=title_color)
        
        # Add config box in top-right
        config_text = f'{config_entities} entities\n{config_features} features'
        ax.text(0.98, 0.98, config_text, transform=ax.transAxes, fontsize=9,
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffffcc', edgecolor='#ff9800', alpha=0.9))
        
        ax.set_xlim(0, max_time * 1.4)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        
        # Add 60ms SLA reference line if applicable
        if max_time > 50:
            ax.axvline(x=60, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='60ms SLA')
    
    # Hide unused axes
    for idx in range(len(stores), 4):
        axes[idx].axis('off')
    
    # Summary box at bottom
    summary_text = f"PROFILING CONFIG: {config_entities} entities × {config_features} features\n"
    summary_text += "Functions shown with time (ms), percentage of total, and call count"
    fig.text(0.5, 0.02, summary_text, ha='center', fontsize=10, 
            bbox=dict(boxstyle='round', facecolor='#e8f4f8', edgecolor='#3498db'))
    
    fig.suptitle('Function-Level Bottleneck Analysis\nTop time-consuming functions per store', 
                fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(os.path.join(output_dir, '05_bottleneck_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 05_bottleneck_breakdown.png")


def chart_10_category_comparison(profile_data: Dict, output_dir: str, benchmark_stores: List[str] = None):
    """
    10 - Grouped bar chart comparing time spent in each category across stores.
    Includes total latency summary for each store.
    Only shows stores that were actually benchmarked.
    """
    categories = ['DB/Store Read', 'Protobuf/Serialization', 'Timestamp Handling', 'Type Checking', 'Other']
    
    # Filter to only stores with breakdown AND that were benchmarked
    all_profile_stores = [s for s in profile_data.keys() if 'breakdown' in profile_data.get(s, {})]
    if benchmark_stores:
        stores = [s for s in all_profile_stores if s in benchmark_stores]
    else:
        stores = all_profile_stores
    
    if not stores:
        print("Skipped: 10_category_comparison.png (no profile data)")
        return
    
    # Get config from first valid store
    config_entities = 50
    config_features = 200
    for store in stores:
        if 'entities' in profile_data.get(store, {}):
            config_entities = profile_data[store]['entities']
            config_features = profile_data[store]['features']
            break
    
    fig, ax = plt.subplots(figsize=(16, 9))
    
    x = np.arange(len(categories))
    width = 0.8 / len(stores)
    colors = {'sqlite': '#3498db', 'redis': '#e74c3c', 'postgres': '#2ecc71', 'dynamodb': '#9b59b6'}
    
    # Build legend labels with total latency
    legend_labels = []
    for i, store in enumerate(stores):
        data = profile_data[store]
        breakdown = data.get('breakdown', {})
        latency = data.get('latency', {})
        total_ms = latency.get('avg_ms', 0)
        p99_ms = latency.get('p99_ms', 0)
        
        values = []
        for cat in categories:
            cat_data = breakdown.get(cat, {})
            values.append(cat_data.get('time_ms', 0))
        
        offset = (i - len(stores)/2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, 
                     color=colors.get(store, '#95a5a6'), alpha=0.85, edgecolor='white')
        
        # Add value labels with percentage
        for bar, val in zip(bars, values):
            if val > 1:
                pct = (val / total_ms * 100) if total_ms > 0 else 0
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                       f'{val:.0f}ms\n({pct:.0f}%)', ha='center', va='bottom', fontsize=8, fontweight='bold')
        
        # Legend with total latency
        legend_labels.append(f'{store.upper()} (Total: {total_ms:.0f}ms, p99: {p99_ms:.0f}ms)')
    
    ax.set_xlabel('Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('Time (ms)', fontsize=12, fontweight='bold')
    ax.set_title(f'Time Breakdown by Category\n{config_entities} entities × {config_features} features', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=15, ha='right', fontsize=11)
    
    # Custom legend with latency info
    handles = [plt.Rectangle((0,0),1,1, color=colors.get(s, '#95a5a6')) for s in stores]
    ax.legend(handles, legend_labels, loc='upper right', fontsize=10, 
             title='Store (Total Latency)', title_fontsize=10)
    
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 60ms SLA reference line
    ax.axhline(y=60, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='60ms SLA Target')
    ax.text(len(categories)-0.5, 62, '60ms SLA', fontsize=9, color='red', fontweight='bold')
    
    # Config box
    config_text = f"Config: {config_entities} entities × {config_features} features"
    ax.text(0.02, 0.98, config_text, transform=ax.transAxes, fontsize=10,
           verticalalignment='top', 
           bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffffcc', edgecolor='#ff9800'))
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '04_category_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 04_category_comparison.png")


def chart_11_optimization_waterfall(profile_data: Dict, output_dir: str, benchmark_stores: List[str] = None):
    """
    11 - Waterfall chart showing cumulative time breakdown for all stores.
    Shows how time is spent for each store with clear entity/feature config.
    Only shows stores that were actually benchmarked.
    """
    # Get all stores with breakdown data, filtered to benchmarked stores
    all_valid = [s for s in ['sqlite', 'redis', 'postgres', 'dynamodb'] 
                if s in profile_data and 'breakdown' in profile_data.get(s, {})]
    if benchmark_stores:
        valid_stores = [s for s in all_valid if s in benchmark_stores]
    else:
        valid_stores = all_valid
    
    if not valid_stores:
        print("Skipped: 11_optimization_waterfall.png (no profile data)")
        return
    
    # Get config
    config_entities = profile_data.get(valid_stores[0], {}).get('entities', 50)
    config_features = profile_data.get(valid_stores[0], {}).get('features', 200)
    
    fig, axes = plt.subplots(len(valid_stores), 1, figsize=(14, 3 * len(valid_stores)))
    if len(valid_stores) == 1:
        axes = [axes]
    
    category_colors = {
        'DB/Store Read': '#3498db',
        'Protobuf/Serialization': '#e74c3c',
        'Timestamp Handling': '#f39c12',
        'Type Checking': '#9b59b6',
        'Entity Processing': '#1abc9c',
        'Other': '#95a5a6'
    }
    store_colors = {'sqlite': '#3498db', 'redis': '#e74c3c', 'postgres': '#2ecc71', 'dynamodb': '#9b59b6'}
    
    for idx, store in enumerate(valid_stores):
        ax = axes[idx]
        data = profile_data[store]
        breakdown = data.get('breakdown', {})
        latency = data.get('latency', {})
        total_latency = latency.get('avg_ms', 100)
        p99_ms = latency.get('p99_ms', 0)
        
        # Sort categories by time
        categories = []
        for cat, cat_data in breakdown.items():
            if cat_data.get('time_ms', 0) > 0.5:
                categories.append((cat, cat_data.get('time_ms', 0), cat_data.get('pct', 0)))
        categories.sort(key=lambda x: x[1], reverse=True)
        
        cumulative = 0
        bars = []
        
        for cat, time_ms, pct in categories:
            color = category_colors.get(cat, '#95a5a6')
            bar = ax.barh(0, time_ms, left=cumulative, color=color, edgecolor='white', height=0.6)
            bars.append((bar, cat, time_ms, pct))
            cumulative += time_ms
        
        # Add labels
        cumulative = 0
        for bar, cat, time_ms, pct in bars:
            mid = cumulative + time_ms / 2
            if time_ms > total_latency * 0.08:  # Only label if > 8%
                ax.text(mid, 0, f'{cat}\n{time_ms:.0f}ms ({pct:.0f}%)', 
                       ha='center', va='center', fontsize=9, fontweight='bold', color='white')
            cumulative += time_ms
        
        # Add SLA marker
        ax.axvline(x=60, color='red', linestyle='--', linewidth=2, alpha=0.7)
        
        # Title with total latency
        sla_status = "[PASS]" if p99_ms < 60 else "[FAIL]"
        ax.set_title(f'{store.upper()} - Total: {total_latency:.0f}ms (p99: {p99_ms:.0f}ms) {sla_status}', 
                    fontsize=12, fontweight='bold', color=store_colors.get(store, '#333'))
        
        ax.set_xlim(0, max(cumulative * 1.15, 80))
        ax.set_ylim(-0.5, 0.5)
        ax.set_xlabel('Time (ms)', fontsize=10)
        ax.set_yticks([])
    
    # Add shared legend at bottom
    legend_patches = [mpatches.Patch(color=category_colors[c], label=c) for c in category_colors]
    legend_patches.append(plt.Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='60ms SLA Target'))
    fig.legend(handles=legend_patches, loc='lower center', ncol=4, fontsize=9, 
              bbox_to_anchor=(0.5, 0.02))
    
    fig.suptitle(f'Time Breakdown Waterfall - Where Latency Goes\n{config_entities} entities × {config_features} features', 
                fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0.08, 1, 0.95])
    plt.savefig(os.path.join(output_dir, '10_optimization_waterfall.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 10_optimization_waterfall.png")


def chart_12_function_heatmap(profile_data: Dict, output_dir: str, benchmark_stores: List[str] = None):
    """
    12 - Heatmap showing function time across stores with total latency info.
    Only shows stores that were actually benchmarked.
    """
    all_stores = [s for s in profile_data.keys() if 'top_functions' in profile_data.get(s, {})]
    if benchmark_stores:
        stores = [s for s in all_stores if s in benchmark_stores]
    else:
        stores = all_stores
    
    if len(stores) < 2:
        print("Skipped: 12_function_heatmap.png (need >= 2 stores)")
        return
    
    # Get config
    config_entities = profile_data.get(stores[0], {}).get('entities', 50)
    config_features = profile_data.get(stores[0], {}).get('features', 200)
    
    # Get common top functions
    all_funcs = set()
    for store in stores:
        for f in profile_data[store].get('top_functions', [])[:15]:
            all_funcs.add(f['name'][:30])
    
    # Build matrix
    func_list = sorted(all_funcs)[:15]
    matrix = []
    
    for store in stores:
        row = []
        func_times = {f['name'][:30]: f['total_ms'] for f in profile_data[store].get('top_functions', [])}
        for func in func_list:
            row.append(func_times.get(func, 0))
        matrix.append(row)
    
    fig, ax = plt.subplots(figsize=(16, 9))
    
    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
    
    ax.set_xticks(range(len(func_list)))
    ax.set_xticklabels(func_list, rotation=45, ha='right', fontsize=9, fontfamily='monospace')
    ax.set_yticks(range(len(stores)))
    
    # Y-axis labels with total latency
    y_labels = []
    for store in stores:
        latency = profile_data[store].get('latency', {})
        total_ms = latency.get('avg_ms', 0)
        p99_ms = latency.get('p99_ms', 0)
        y_labels.append(f'{store.upper()} ({total_ms:.0f}ms total, p99:{p99_ms:.0f}ms)')
    ax.set_yticklabels(y_labels, fontsize=10)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Time (ms)', fontsize=11)
    
    # Add text annotations
    max_val = max(max(row) for row in matrix) if matrix and any(matrix) else 1
    for i in range(len(stores)):
        for j in range(len(func_list)):
            val = matrix[i][j]
            if val > 0.5:
                color = 'white' if val > max_val * 0.5 else 'black'
                ax.text(j, i, f'{val:.0f}', ha='center', va='center', fontsize=8, color=color, fontweight='bold')
    
    # Config box
    config_text = f'Config: {config_entities} entities × {config_features} features'
    ax.text(0.02, 1.02, config_text, transform=ax.transAxes, fontsize=10,
           verticalalignment='bottom',
           bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffffcc', edgecolor='#ff9800'))
    
    ax.set_title('Function Time Heatmap Across Stores\nComparing bottlenecks: darker = more time spent', 
                fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '11_function_heatmap.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 11_function_heatmap.png")


def recategorize_functions(top_functions: list, total_ms: float) -> dict:
    """
    Re-categorize function times using comprehensive patterns.
    Returns a breakdown dict with time_ms and pct for each category.
    Ensures all time is accounted for (adds untracked time to Other).
    """
    # Comprehensive patterns for each category
    CATEGORY_PATTERNS = {
        'DB/Store Read': [
            # Generic
            'online_read', '_get_online_features_from_online_store',
            'execute', 'fetchall', '_make_request', 'send', 'recv',
            # SQLite
            'sqlite3.Cursor', 'sqlite3',
            # Redis - network I/O and pipeline
            '_read_response', 'read_response', 'readline', '_execute_pipeline',
            'execute_command', 'pipeline_execute_command', 'hmget', 'mget',
            '_get_features_for_entity', 'pack', 'encode',
            # Postgres
            '_execute_gen', '_execute_send', 'wait', '_process_rows', '_maybe_prepare',
            # DynamoDB - batch operations and response parsing
            'batch_get_item', '_process_batch_get_response', '_handle_structure',
            '_parse_shape', '_handle_map', 'deserialize', '_deserialize',
            '_SSLSocket', 'ssl.read', '_bytes_from_decode_data', 'b64decode',
        ],
        'Protobuf/Serialization': [
            '_convert_rows_to_protobuf', 'construct_response_feature_vector',
            'SerializeToString', 'ParseFromString', 'MessageToDict',
            'to_proto', 'from_proto', '_serialized_to_proto',
            '_convert_redis_values_to_protobuf', 'RepeatedCompositeContainer',
        ],
        'Timestamp Handling': [
            'FromDatetime', 'convert_timestamp', '_CheckTimestampValid',
            'ToDatetime', 'FromSeconds', 'ToSeconds',
            'timegm', 'utctimetuple', 'fromtimestamp', 'datetime.replace',
        ],
        'Type Checking': [
            'check_type_internal', 'builtin_checker_lookup', 'get_origin',
            'isinstance',
        ],
    }
    
    breakdown = {cat: {'time_ms': 0, 'pct': 0, 'functions': []} for cat in CATEGORY_PATTERNS}
    breakdown['Other'] = {'time_ms': 0, 'pct': 0, 'functions': []}
    
    tracked_time = 0
    for func in top_functions:
        name = func.get('name', '')
        time_ms = func.get('total_ms', 0)
        tracked_time += time_ms
        
        categorized = False
        for category, patterns in CATEGORY_PATTERNS.items():
            if any(p in name for p in patterns):
                breakdown[category]['time_ms'] += time_ms
                breakdown[category]['functions'].append(func)
                categorized = True
                break
        
        if not categorized:
            breakdown['Other']['time_ms'] += time_ms
            breakdown['Other']['functions'].append(func)
    
    # Add untracked time (from functions not in top_functions) to Other
    untracked_time = total_ms - tracked_time
    if untracked_time > 0:
        breakdown['Other']['time_ms'] += untracked_time
    
    # Calculate percentages (should now sum to 100%)
    for cat in breakdown:
        if total_ms > 0:
            breakdown[cat]['pct'] = (breakdown[cat]['time_ms'] / total_ms) * 100
    
    return breakdown


def load_profile_data(results_dir: str, benchmark_results: Dict = None) -> Dict:
    """
    Load profiling data from bottleneck_analysis.json if available.
    Merges benchmark latency to avoid showing inflated profiler overhead.
    Re-categorizes functions using improved patterns.
    """
    profile_path = os.path.join(results_dir, 'profile', 'bottleneck_analysis.json')
    if not os.path.exists(profile_path):
        # Try parent directory
        profile_path = os.path.join(os.path.dirname(results_dir), 'profile', 'bottleneck_analysis.json')
    
    if not os.path.exists(profile_path):
        return {}
    
    with open(profile_path) as f:
        profile_data = json.load(f)
    
    # Merge benchmark latency (clean runs) instead of profiled latency (has ~30% overhead)
    if benchmark_results:
        for store, pdata in profile_data.items():
            if store not in benchmark_results:
                continue
            
            bench = benchmark_results[store]
            target_entities = pdata.get('entities', 50)
            
            # Find matching latency from benchmark
            for lat in bench.get('latency', []):
                if lat.get('num_entities') == target_entities:
                    bench_avg = lat.get('mean', lat.get('p50', 0))
                    bench_p99 = lat.get('p99', 0)
                    profile_avg = pdata.get('latency', {}).get('avg_ms', bench_avg)
                    
                    # Use benchmark latency (not profiled)
                    pdata['latency'] = {
                        'avg_ms': bench_avg,
                        'p50_ms': lat.get('p50', bench_avg),
                        'p99_ms': bench_p99,
                        'profiled_avg_ms': profile_avg  # Keep original for reference
                    }
                    
                    # Rescale function times based on benchmark latency
                    scale = bench_avg / profile_avg if profile_avg > 0 else 1
                    if 'top_functions' in pdata:
                        for func in pdata['top_functions']:
                            func['total_ms'] = func.get('total_ms', 0) * scale
                    
                    # Re-categorize using improved patterns (overwrites old breakdown)
                    if 'top_functions' in pdata:
                        pdata['breakdown'] = recategorize_functions(
                            pdata['top_functions'], 
                            bench_avg
                        )
                    break
    
    return profile_data


def chart_cross_reference_comparison(results_base: str, output_dir: str, refs: List[str] = None):
    """
    Generate optimization impact comparison chart.
    Focused on showcasing the performance improvements from Feast optimizations.
    Includes both entity scaling and feature scaling comparisons.
    """
    if refs is None:
        refs = ["master", "v0.60.0", "optimized"]
    
    stores = ["sqlite", "redis", "postgres", "dynamodb"]
    entity_counts = [1, 10, 50, 100, 200, 500]
    feature_counts = [5, 25, 50, 100, 150, 200]
    SLA_MS = 60
    
    store_colors = {"sqlite": "#2ecc71", "redis": "#e74c3c", "postgres": "#3498db", "dynamodb": "#f39c12"}
    store_labels = {"sqlite": "SQLite", "redis": "Redis", "postgres": "PostgreSQL", "dynamodb": "DynamoDB"}
    
    # Load entity_scaling data
    entity_data = {}
    for ref in refs:
        entity_data[ref] = {}
        for store in stores:
            json_path = os.path.join(results_base, ref, store, "entity_scaling", "benchmark_results.json")
            if os.path.exists(json_path):
                with open(json_path) as f:
                    entity_data[ref][store] = json.load(f)
                continue
            # Fallback to old structure
            json_path = os.path.join(results_base, ref, store, "benchmark_results.json")
            if os.path.exists(json_path):
                with open(json_path) as f:
                    entity_data[ref][store] = json.load(f)
    
    # Load feature_scaling data
    feature_data = {}
    for ref in refs:
        feature_data[ref] = {}
        for store in stores:
            json_path = os.path.join(results_base, ref, store, "feature_scaling", "benchmark_results.json")
            if os.path.exists(json_path):
                with open(json_path) as f:
                    feature_data[ref][store] = json.load(f)
    
    # Helper to get p99 latency for entity scaling
    def get_entity_p99(ref, store, entities):
        if store not in entity_data.get(ref, {}):
            return None
        lat_data = entity_data[ref][store].get("latency", [])
        return next((l["p99"] for l in lat_data if l["num_entities"] == entities), None)
    
    # Helper to get p99 latency for feature scaling
    def get_feature_p99(ref, store, features):
        if store not in feature_data.get(ref, {}):
            return None
        lat_data = feature_data[ref][store].get("latency", [])
        return next((l["p99"] for l in lat_data if l.get("num_features") == features), None)
    
    # Check if we have feature scaling data
    has_feature_data = any(feature_data.get(ref, {}) for ref in refs)
    
    # Create figure with 4 panels (2x2) - cleaner, more reliable presentation
    fig = plt.figure(figsize=(16, 12))
    nrows, ncols = 2, 2
    
    # =========================================================================
    # Panel 1: Entity Scaling - All 3 References @ 50 entities
    # Order: v0.60.0 → Master → Optimized (showing improvement progression)
    # =========================================================================
    ax1 = fig.add_subplot(nrows, ncols, 1)
    
    x = np.arange(len(stores))
    width = 0.25
    
    v060_50 = [get_entity_p99("v0.60.0", s, 50) or 0 for s in stores]
    master_50 = [get_entity_p99("master", s, 50) or 0 for s in stores]
    opt_50 = [get_entity_p99("optimized", s, 50) or 0 for s in stores]
    
    bars1 = ax1.bar(x - width, v060_50, width, label='v0.60.0 (Baseline)', color='#e74c3c', edgecolor='white', linewidth=1.5)
    bars2 = ax1.bar(x, master_50, width, label='Master', color='#f39c12', edgecolor='white', linewidth=1.5)
    bars3 = ax1.bar(x + width, opt_50, width, label='Optimized', color='#2ecc71', edgecolor='white', linewidth=1.5)
    
    ax1.axhline(y=SLA_MS, color="purple", linestyle="--", linewidth=2, alpha=0.7, label=f"{SLA_MS}ms SLA")
    
    # Add improvement % labels (v0.60.0 vs optimized)
    for i, (v, o) in enumerate(zip(v060_50, opt_50)):
        if v > 0 and o > 0:
            pct = ((v - o) / v) * 100
            ax1.annotate(f'{pct:+.0f}%', xy=(x[i] + width, o + 5), ha='center', 
                        fontsize=9, fontweight='bold', color='#27ae60')
    
    ax1.set_ylabel("P99 Latency (ms)", fontsize=12, fontweight="bold")
    ax1.set_title("ENTITY SCALING: 50 Entities × 200 Features\n(v0.60.0 → Master → Optimized)", fontsize=13, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels([store_labels.get(s, s) for s in stores], fontsize=11)
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_ylim(0, max(master_50 + v060_50 + [1]) * 1.2)
    
    # =========================================================================
    # Panel 2: Feature Scaling - All 3 References @ 200 features
    # Order: v0.60.0 → Master → Optimized (showing improvement progression)
    # =========================================================================
    ax2 = fig.add_subplot(nrows, ncols, 2)
    
    if has_feature_data:
        v060_200f = [get_feature_p99("v0.60.0", s, 200) or 0 for s in stores]
        master_200f = [get_feature_p99("master", s, 200) or 0 for s in stores]
        opt_200f = [get_feature_p99("optimized", s, 200) or 0 for s in stores]
        
        bars1 = ax2.bar(x - width, v060_200f, width, label='v0.60.0 (Baseline)', color='#e74c3c', edgecolor='white', linewidth=1.5)
        bars2 = ax2.bar(x, master_200f, width, label='Master', color='#f39c12', edgecolor='white', linewidth=1.5)
        bars3 = ax2.bar(x + width, opt_200f, width, label='Optimized', color='#2ecc71', edgecolor='white', linewidth=1.5)
        
        ax2.axhline(y=SLA_MS, color="purple", linestyle="--", linewidth=2, alpha=0.7, label=f"{SLA_MS}ms SLA")
        
        # Add improvement % labels (v0.60.0 vs optimized - consistent with entity scaling)
        for i, (v, o) in enumerate(zip(v060_200f, opt_200f)):
            if v > 0 and o > 0:
                pct = ((v - o) / v) * 100
                ax2.annotate(f'{pct:+.0f}%', xy=(x[i] + width, o + 5), ha='center', 
                            fontsize=9, fontweight='bold', color='#27ae60')
        
        ax2.set_ylabel("P99 Latency (ms)", fontsize=12, fontweight="bold")
        ax2.set_title("FEATURE SCALING: 50 Entities × 200 Features\n(v0.60.0 → Master → Optimized)", fontsize=13, fontweight="bold")
        ax2.set_xticks(x)
        ax2.set_xticklabels([store_labels.get(s, s) for s in stores], fontsize=11)
        ax2.legend(loc="upper right", fontsize=9)
        ax2.grid(axis="y", alpha=0.3)
        max_val = max(v060_200f + master_200f + opt_200f + [1])
        ax2.set_ylim(0, max_val * 1.2)
    else:
        ax2.text(0.5, 0.5, "No feature scaling data available", transform=ax2.transAxes,
                 ha='center', va='center', fontsize=14, color='gray')
        ax2.axis('off')
    
    # =========================================================================
    # Panel 3: DynamoDB Deep Dive - Full Scaling Curve Comparison
    # Order: v0.60.0 → Master → Optimized (consistent with other panels)
    # =========================================================================
    ax3 = fig.add_subplot(nrows, ncols, 3)
    
    # Show all 3 refs for DynamoDB in correct order
    for ref, color, label, ls in [("v0.60.0", "#e74c3c", "v0.60.0 (Baseline)", "-"), 
                                   ("master", "#f39c12", "Master", "-"),
                                   ("optimized", "#2ecc71", "Optimized", "-")]:
        if "dynamodb" in entity_data.get(ref, {}):
            lat_data = entity_data[ref]["dynamodb"].get("latency", [])
            entities = sorted([l["num_entities"] for l in lat_data])
            p99s = [next((l["p99"] for l in lat_data if l["num_entities"] == e), 0) for e in entities]
            ax3.plot(entities, p99s, marker="o", linewidth=3, markersize=8,
                    label=f"DynamoDB ({label})", color=color, linestyle=ls)
    
    ax3.axhline(y=SLA_MS, color="purple", linestyle="--", linewidth=2, label=f"{SLA_MS}ms SLA")
    ax3.fill_between([0, 600], 0, SLA_MS, alpha=0.15, color='green')
    
    # Add annotations for key points (v0.60.0 baseline vs Optimized)
    baseline_50 = get_entity_p99("v0.60.0", "dynamodb", 50)
    opt_50_ent = get_entity_p99("optimized", "dynamodb", 50)
    if baseline_50 and opt_50_ent:
        ax3.annotate(f'{baseline_50:.0f}ms', xy=(50, baseline_50), 
                    xytext=(70, baseline_50 + 30), fontsize=10,
                    arrowprops=dict(arrowstyle='->', color='#e74c3c'))
        ax3.annotate(f'{opt_50_ent:.0f}ms', xy=(50, opt_50_ent), 
                    xytext=(70, opt_50_ent - 30), fontsize=10,
                    arrowprops=dict(arrowstyle='->', color='#2ecc71'))
        # Show improvement
        saved = baseline_50 - opt_50_ent
        ax3.annotate(f'-{saved:.0f}ms ({saved/baseline_50*100:.0f}%)', xy=(50, (baseline_50 + opt_50_ent)/2),
                    xytext=(120, (baseline_50 + opt_50_ent)/2), fontsize=9, fontweight='bold',
                    color='#27ae60', arrowprops=dict(arrowstyle='->', color='#27ae60', lw=1.5))
    
    ax3.set_xlabel("Entity Count", fontsize=12, fontweight="bold")
    ax3.set_ylabel("P99 Latency (ms)", fontsize=12, fontweight="bold")
    ax3.set_title("DynamoDB: Entity Scaling Comparison\n(Production Cloud Store)", fontsize=13, fontweight="bold")
    ax3.legend(loc="upper left", fontsize=10)
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(0, 550)
    
    # =========================================================================
    # Panel 4: Executive Summary - Clean table format
    # =========================================================================
    ax4 = fig.add_subplot(nrows, ncols, 4)
    ax4.axis("off")
    
    # Calculate comprehensive stats (comparing v0.60.0 baseline to optimized)
    avg_improvement = np.mean([((get_entity_p99("v0.60.0", s, 50) or 0) - (get_entity_p99("optimized", s, 50) or 0)) / 
                               (get_entity_p99("v0.60.0", s, 50) or 1) * 100 
                               for s in stores if get_entity_p99("v0.60.0", s, 50)])
    
    total_ms_saved = sum([(get_entity_p99("v0.60.0", s, 50) or 0) - (get_entity_p99("optimized", s, 50) or 0) 
                          for s in stores])
    
    best_store = min(stores, key=lambda s: get_entity_p99("optimized", s, 50) or 999)
    best_lat = get_entity_p99("optimized", best_store, 50)
    
    # Title
    ax4.text(0.5, 0.98, "P99 LATENCY SUMMARY (ms) - 50 Entities × 200 Features", transform=ax4.transAxes,
             fontsize=12, fontweight='bold', ha='center', va='top')
    ax4.text(0.5, 0.94, "Entity Scaling (top) | Feature Scaling (bottom)", 
             transform=ax4.transAxes, fontsize=9, ha='center', va='top', style='italic', color='#666')
    
    # Create table data - Show all 3 refs for both scenarios
    table_data = [["Store", "v0.60.0", "Master", "Optimized", "Saved"]]
    
    # Entity scaling row
    table_data.append(["--- ENTITY SCALING ---", "", "", "", ""])
    for store in stores:
        ve = get_entity_p99("v0.60.0", store, 50) or 0
        me = get_entity_p99("master", store, 50) or 0
        oe = get_entity_p99("optimized", store, 50) or 0
        saved = ve - oe if ve > 0 and oe > 0 else 0
        
        table_data.append([
            store_labels.get(store, store),
            f"{ve:.0f}" if ve else "-",
            f"{me:.0f}" if me else "-",
            f"{oe:.0f}" if oe else "-",
            f"-{saved:.0f}ms" if saved > 0 else "-"
        ])
    
    # Feature scaling row
    table_data.append(["--- FEATURE SCALING ---", "", "", "", ""])
    for store in stores:
        vf = get_feature_p99("v0.60.0", store, 200) or 0
        mf = get_feature_p99("master", store, 200) or 0
        of = get_feature_p99("optimized", store, 200) or 0
        saved = vf - of if vf > 0 and of > 0 else 0
        
        table_data.append([
            store_labels.get(store, store),
            f"{vf:.0f}" if vf else "-",
            f"{mf:.0f}" if mf else "-",
            f"{of:.0f}" if of else "-",
            f"-{saved:.0f}ms" if saved > 0 else "-"
        ])
    
    # Create the table with better colors
    table = ax4.table(
        cellText=table_data,
        cellLoc='center',
        loc='upper center',
        bbox=[0.02, 0.42, 0.96, 0.50]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    
    # Style header row
    for j in range(5):
        table[(0, j)].set_facecolor('#34495e')
        table[(0, j)].set_text_props(fontweight='bold', color='white')
        table[(0, j)].set_height(0.04)
    
    # Style data rows
    for i in range(1, len(table_data)):
        cell_text = table_data[i][0]
        is_section_header = "---" in cell_text
        
        for j in range(5):
            table[(i, j)].set_height(0.04)
            
            if is_section_header:
                # Section header row
                table[(i, j)].set_facecolor('#2c3e50')
                table[(i, j)].set_text_props(fontweight='bold', color='white', fontsize=8)
            else:
                # Data row
                bg_color = '#f8f9fa' if i % 2 == 0 else '#ecf0f1'
                table[(i, j)].set_facecolor(bg_color)
                
                # Highlight Optimized column (j=3)
                if j == 3:
                    table[(i, j)].set_facecolor('#d5f5e3')
                    table[(i, j)].set_text_props(fontweight='bold')
                # Highlight Saved column (j=4)
                if j == 4:
                    table[(i, j)].set_text_props(fontweight='bold', color='#27ae60')
    
    # Key metrics section
    metrics_y = 0.38
    ax4.text(0.5, metrics_y, "KEY FINDINGS", transform=ax4.transAxes,
             fontsize=11, fontweight='bold', ha='center', va='top')
    
    # Calculate feature scaling improvements (v0.60.0 → Optimized)
    feature_improvements = []
    for store in stores:
        vf = get_feature_p99("v0.60.0", store, 200) or 0
        of = get_feature_p99("optimized", store, 200) or 0
        if vf > 0 and of > 0:
            feature_improvements.append(((vf - of) / vf) * 100)
    avg_feature_imp = np.mean(feature_improvements) if feature_improvements else 0
    
    summary_text = f"""
Entity Scaling (v0.60.0 → Optimized): {avg_improvement:+.1f}%
Feature Scaling (v0.60.0 → Optimized): {avg_feature_imp:+.1f}%
"""
    
    ax4.text(0.5, metrics_y - 0.05, summary_text, transform=ax4.transAxes, fontsize=10,
             verticalalignment="top", ha='center', fontfamily='monospace')
    
    fig.suptitle("Feast Feature Store - Optimization Impact Analysis", 
                 fontsize=18, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, "01_cross_reference_comparison.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: 01_cross_reference_comparison.png")


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark visualization charts")
    parser.add_argument("--dirs", nargs='+', help="Result directories (for single-ref mode)")
    parser.add_argument("--names", nargs='+', help="Store names (for single-ref mode)")
    parser.add_argument("--output", default="results/charts", help="Output directory")
    parser.add_argument("--compare-refs", action="store_true", help="Generate cross-reference comparison chart")
    parser.add_argument("--results-base", default="results", help="Base results directory (for --compare-refs)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FEAST BENCHMARK CHART GENERATOR")
    print("=" * 60)
    
    # Cross-reference comparison mode
    if args.compare_refs:
        print("Mode: Cross-reference comparison")
        print(f"Results base: {args.results_base}/")
        print(f"Output: {args.output}/")
        print("-" * 60)
        chart_cross_reference_comparison(args.results_base, args.output)
        print("-" * 60)
        print("Done! 1 comparison chart generated.")
        print("=" * 60)
        return
    
    # Single-ref mode (original behavior)
    if not args.dirs or not args.names:
        print("Error: --dirs and --names required (or use --compare-refs)")
        return
    
    if len(args.dirs) != len(args.names):
        print("Error: --dirs and --names must have same length")
        return
    
    os.makedirs(args.output, exist_ok=True)
    
    # Load entity_scaling results for chart_01 (latency by entities)
    entity_results = load_scenario_results(args.dirs, args.names, 'entity_scaling')
    
    # Load feature_scaling results for chart_01b (latency by features)
    feature_results = load_scenario_results(args.dirs, args.names, 'feature_scaling')
    
    # Fallback: load all results (old structure compatibility)
    if not entity_results and not feature_results:
        entity_results = load_results(args.dirs, args.names)
    
    # Use entity_scaling results as primary (for executive summary, SLA analysis, etc.)
    results = entity_results if entity_results else feature_results
    
    if not results:
        print("No results found!")
        return
    
    print(f"Stores: {', '.join(results.keys())}")
    print(f"Entity scaling data: {len(entity_results)} stores" if entity_results else "No entity scaling data")
    print(f"Feature scaling data: {len(feature_results)} stores" if feature_results else "No feature scaling data")
    print(f"Output: {args.output}/")
    print("-" * 60)
    
    # Load profiling data early so charts 04 and 08 can use it
    profile_data = load_profile_data(os.path.dirname(args.dirs[0]), results)
    
    chart_count = 0
    
    # Chart 01: Entity scaling (if data available)
    if entity_results:
        chart_01_latency_by_entities(entity_results, args.output)
        chart_count += 1
    
    # Chart 01b: Feature scaling (if data available)
    if feature_results:
        chart_01b_latency_by_features(feature_results, args.output)
        chart_count += 1
    
    # Executive summary and SLA charts use entity_scaling data
    if results:
        chart_06_executive_summary(results, args.output)
        chart_07_production_sla(results, args.output)
        chart_count += 2
    
    # Generate bottleneck analysis charts if profile data available
    benchmark_stores = list(results.keys())
    if profile_data:
        print("-" * 60)
        print("Generating bottleneck analysis charts...")
        chart_09_bottleneck_breakdown(profile_data, args.output, benchmark_stores)
        chart_10_category_comparison(profile_data, args.output, benchmark_stores)
        chart_count += 2
    
    print("-" * 60)
    print(f"Done! {chart_count} charts generated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
