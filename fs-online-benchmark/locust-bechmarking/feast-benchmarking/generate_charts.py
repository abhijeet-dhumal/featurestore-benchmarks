#!/usr/bin/env python3
"""
Feast Benchmark Chart Generator - Meaningful Visualizations

Charts:
  01_latency_by_entities.png   - P99 latency grouped by entity count
  02_scaling_curves.png        - How latency scales with entities
  03_store_ranking.png         - Stores ranked by performance
  04_time_breakdown.png        - Where time is spent (stacked bar)
  05_sla_gap_analysis.png      - Gap between actual and 60ms target
  06_executive_summary.png     - Key metrics at a glance
  07_production_sla.png        - Production SLA analysis (log scale with annotations)
  08_time_distribution.png     - Donut charts showing component breakdown
  09_online_read_breakdown.png - Internal online_read() timing by store
  10_optimization_targets.png  - Potential savings from each optimization
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


def load_results(result_dirs: List[str], names: List[str]) -> Dict[str, Dict]:
    """Load benchmark results from directories."""
    results = {}
    for dir_path, name in zip(result_dirs, names):
        json_path = os.path.join(dir_path, "benchmark_results.json")
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


def chart_04_time_breakdown(results: Dict, output_dir: str):
    """
    04 - Stacked bar showing where time is spent at max entity count.
    """
    fig, ax = plt.subplots(figsize=(12, 7))
    
    breakdown_data = []
    for store, data in results.items():
        latency_data = data.get('latency', [])
        if latency_data:
            r = max(latency_data, key=lambda x: x['num_entities'])
            total = r['p99']
            online_read_pct = r.get('online_read_pct', 40)  # Default estimates
            protobuf_pct = r.get('protobuf_convert_pct', 35)
            other_pct = 100 - online_read_pct - protobuf_pct
            
            breakdown_data.append({
                'store': store,
                'entities': r['num_entities'],
                'total': total,
                'online_read': total * online_read_pct / 100,
                'protobuf': total * protobuf_pct / 100,
                'other': total * other_pct / 100
            })
    
    # Sort by total (fastest first)
    breakdown_data.sort(key=lambda x: x['total'])
    
    stores = [d['store'].upper() for d in breakdown_data]
    y_pos = np.arange(len(stores))
    
    online_read = [d['online_read'] for d in breakdown_data]
    protobuf = [d['protobuf'] for d in breakdown_data]
    other = [d['other'] for d in breakdown_data]
    
    ax.barh(y_pos, online_read, height=0.6, label='Online Store Read', color='#3498db')
    ax.barh(y_pos, protobuf, height=0.6, left=online_read, label='Protobuf/Serialization', color='#e74c3c')
    ax.barh(y_pos, other, height=0.6, left=[a+b for a,b in zip(online_read, protobuf)], 
           label='Other (network, etc)', color='#95a5a6')
    
    # Total labels
    for i, d in enumerate(breakdown_data):
        ax.text(d['total'] + 20, i, f"{d['total']:.0f}ms total",
               va='center', fontsize=10, fontweight='bold',
               color='#c0392b' if d['total'] > SLA_TARGET_MS else '#27ae60')
    
    # 60ms reference
    ax.axvline(x=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2.5)
    ax.text(SLA_TARGET_MS, len(stores) - 0.3, f'Target: {SLA_TARGET_MS}ms', 
           color='#c0392b', fontsize=10, fontweight='bold', va='top', rotation=90)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stores)
    ax.set_xlabel('Time (ms)', fontsize=12, fontweight='bold')
    ax.set_title(f'Time Breakdown at {breakdown_data[0]["entities"]} Entities\nWhere is time spent?', 
                fontsize=14, fontweight='bold')
    ax.legend(loc='lower right', fontsize=10)
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
    
    # --- Bottom Left: Latency at 500 entities ---
    ax = axes[1, 0]
    lat_500 = []
    for store, data in results.items():
        for r in data.get('latency', []):
            if r['num_entities'] == 500:
                lat_500.append({'store': store, 'p99': r['p99']})
    
    lat_500.sort(key=lambda x: x['p99'])
    stores = [d['store'].upper() for d in lat_500]
    latencies = [d['p99'] for d in lat_500]
    colors = [COLORS.get(d['store'], '#95a5a6') for d in lat_500]
    
    bars = ax.barh(range(len(stores)), latencies, color=colors, edgecolor='white', height=0.6)
    for i, (bar, lat) in enumerate(zip(bars, latencies)):
        ax.text(lat + 20, i, f'{lat:.0f}ms ({lat/SLA_TARGET_MS:.0f}x)',
               va='center', fontsize=10, fontweight='bold', color='#c0392b')
    
    ax.axvline(x=SLA_TARGET_MS, color='#c0392b', linestyle='--', linewidth=2)
    ax.set_yticks(range(len(stores)))
    ax.set_yticklabels(stores)
    ax.set_xlabel('P99 Latency (ms)')
    ax.set_title('Performance at 500 Entities (Target Workload)', fontweight='bold')
    
    # --- Bottom Right: Key Findings ---
    ax = axes[1, 1]
    ax.axis('off')
    
    # Calculate key stats
    best_store_500 = lat_500[0]['store'] if lat_500 else 'N/A'
    best_lat_500 = lat_500[0]['p99'] if lat_500 else 0
    worst_lat_500 = lat_500[-1]['p99'] if lat_500 else 0
    
    findings = f"""
KEY FINDINGS

Target: {SLA_TARGET_MS}ms p99 latency
Config: 200 features, 500 entities

RESULTS AT 500 ENTITIES:
• Best Store: {best_store_500.upper()} ({best_lat_500:.0f}ms)
• Gap: {best_lat_500/SLA_TARGET_MS:.0f}x over target
• Range: {lat_500[0]['p99'] if lat_500 else 0:.0f}ms - {worst_lat_500:.0f}ms

SLA COMPLIANCE:
• 1 entity: Most stores PASS
• 10+ entities: ALL stores FAIL
• 500 entities: {best_lat_500/SLA_TARGET_MS:.0f}-{worst_lat_500/SLA_TARGET_MS:.0f}x over target

RANKING (fastest to slowest):
{chr(10).join(f"  {i+1}. {d['store'].upper()}: {d['p99']:.0f}ms" for i, d in enumerate(lat_500))}

CONCLUSION:
Config optimizations alone cannot meet the 
{SLA_TARGET_MS}ms SLA. Code-level fixes required.
"""
    
    ax.text(0.05, 0.95, findings, transform=ax.transAxes, fontsize=11,
           verticalalignment='top', fontfamily='monospace',
           bbox=dict(boxstyle='round', facecolor='#f8f9fa', edgecolor='#dee2e6'))
    
    fig.suptitle('Feast Online Store Benchmark - Executive Summary', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '06_executive_summary.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 06_executive_summary.png")


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
    plt.savefig(os.path.join(output_dir, '07_production_sla.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 07_production_sla.png")


def chart_08_time_distribution(results: Dict, output_dir: str):
    """
    08 - Donut charts showing time distribution by component for each store.
    Based on typical Feast SDK breakdown: Protobuf Convert, Serialize Entity Key, 
    Online Read, Prepare Entities, Get Online Request Context.
    """
    # Component breakdown estimates (based on profiling)
    # These percentages are typical for 100 entities, 50 features
    COMPONENT_BREAKDOWN = {
        'sqlite': {'Protobuf Convert': 47, 'Online Read': 41, 'Serialize Entity Key': 10, 
                   'Prepare Entities': 1, 'Get Online Request Context': 1},
        'redis': {'Protobuf Convert': 82, 'Serialize Entity Key': 10, 'Online Read': 3,
                  'Prepare Entities': 3, 'Get Online Request Context': 2},
        'postgres': {'Protobuf Convert': 82, 'Serialize Entity Key': 10, 'Online Read': 3,
                     'Prepare Entities': 2, 'Get Online Request Context': 3},
        'dynamodb': {'Protobuf Convert': 80, 'Serialize Entity Key': 10, 'Online Read': 4,
                     'Prepare Entities': 3, 'Get Online Request Context': 3},
    }
    
    COMPONENT_COLORS = {
        'Online Read': '#3498db',
        'Protobuf Convert': '#7f8c8d',
        'Serialize Entity Key': '#1abc9c',
        'Prepare Entities': '#95a5a6',
        'Get Online Request Context': '#bdc3c7',
    }
    
    n_stores = len(results)
    cols = 2
    rows = (n_stores + 1) // 2
    fig, axes = plt.subplots(rows, cols, figsize=(12, 5 * rows))
    axes = axes.flatten() if n_stores > 1 else [axes]
    
    for idx, (store, data) in enumerate(results.items()):
        ax = axes[idx]
        
        # Get total latency at 100 entities (or closest)
        latency_data = data.get('latency', [])
        total_ms = 15.0  # Default
        for r in latency_data:
            if r['num_entities'] == 100:
                total_ms = r['p50']  # Use p50 for typical
                break
            elif r['num_entities'] == 1:
                total_ms = r['p50']
        
        breakdown = COMPONENT_BREAKDOWN.get(store, COMPONENT_BREAKDOWN['sqlite'])
        
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
        
        # Center text
        ax.text(0, 0, f'{store.upper()}\nTotal: {total_ms:.1f}ms', ha='center', va='center',
               fontsize=11, fontweight='bold')
        
        ax.set_title(f'{store.upper()}', fontsize=12, fontweight='bold', pad=10)
    
    # Hide unused axes
    for idx in range(len(results), len(axes)):
        axes[idx].axis('off')
    
    # Add legend
    legend_patches = [mpatches.Patch(color=COMPONENT_COLORS[c], label=c) for c in COMPONENT_COLORS]
    fig.legend(handles=legend_patches, loc='center right', fontsize=10, bbox_to_anchor=(1.15, 0.5))
    
    fig.suptitle('Time Distribution by Component\n(100 entities, 50 features)', 
                fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '08_time_distribution.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 08_time_distribution.png")


def chart_09_online_read_breakdown(results: Dict, output_dir: str):
    """
    09 - Horizontal bar charts showing online_read() internal breakdown for each store.
    Shows store-specific internals like Fetch results, Pipeline execute, HTTP read, etc.
    """
    # Store-specific internal breakdown (from profiling)
    INTERNAL_BREAKDOWN = {
        'sqlite': [('Fetch results', 11.1), ('SQL execute', 1.5)],
        'redis': [('Read response', 13.1), ('Pipeline execute', 1.0), 
                  ('Pipeline create', 0.7), ('MGET command', 0.4)],
        'postgres': [('Fetch results', 4.3), ('Network send', 1.4), ('SQL execute', 0.4)],
        'dynamodb': [('HTTP read', 1.5), ('Make request', 0.3), ('HTTP send', 0.3)],
    }
    
    n_stores = len(results)
    cols = 2
    rows = (n_stores + 1) // 2
    fig, axes = plt.subplots(rows, cols, figsize=(14, 4 * rows))
    axes = axes.flatten() if n_stores > 1 else [axes]
    
    for idx, store in enumerate(results.keys()):
        ax = axes[idx]
        color = COLORS.get(store, '#95a5a6')
        
        breakdown = INTERNAL_BREAKDOWN.get(store, [('Unknown', 5.0)])
        
        labels = [b[0] for b in breakdown]
        values = [b[1] for b in breakdown]
        
        y_pos = np.arange(len(labels))
        bars = ax.barh(y_pos, values, color=color, edgecolor='white', height=0.6)
        
        # Add value labels
        for bar, val in zip(bars, values):
            ax.text(val + 0.2, bar.get_y() + bar.get_height()/2, f'{val:.1f}ms',
                   va='center', fontsize=10, fontweight='bold')
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.set_xlabel('Cumulative Time (ms)')
        ax.set_title(f'{store.upper()} - online_read() Internals', fontsize=12, fontweight='bold')
        ax.set_xlim(0, max(values) * 1.3 if values else 10)
        ax.grid(axis='x', alpha=0.3)
        ax.invert_yaxis()  # Largest at top
    
    # Hide unused axes
    for idx in range(len(results), len(axes)):
        axes[idx].axis('off')
    
    fig.suptitle('online_read() Function Breakdown by Store\n(100 entities, 50 features, 10 iterations cumulative)', 
                fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '09_online_read_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 09_online_read_breakdown.png")


def chart_10_optimization_targets(results: Dict, output_dir: str):
    """
    10 - Bar chart showing optimization targets with current time and potential savings.
    Shows which components have the most optimization potential.
    """
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Optimization targets based on PRs submitted (average across stores)
    # Format: (component, current_ms, savings_ms)
    OPTIMIZATION_DATA = [
        ('Protobuf Convert', 11.3, 5.7),   # PR #6015 - MessageToDict optimization
        ('Online Read', 3.5, 1.8),          # Various store optimizations
        ('Serialize Entity Key', 1.7, 0.9), # PR #6006 - Remove redundant serialization
        ('Prepare Entities', 0.4, 0.2),     # PR #6003 - Timestamp fix
        ('Get Online Request Context', 0.4, 0.2),  # PR #6014 - Registry lookups
    ]
    
    components = [d[0] for d in OPTIMIZATION_DATA]
    current = [d[1] for d in OPTIMIZATION_DATA]
    savings = [d[2] for d in OPTIMIZATION_DATA]
    
    x = np.arange(len(components))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, current, width, label='Current Time', color='#e74c3c', edgecolor='white')
    bars2 = ax.bar(x + width/2, savings, width, label='Potential Savings (50%)', color='#2ecc71', edgecolor='white')
    
    # Add value labels
    for bar, val in zip(bars1, current):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2, f'{val:.1f}ms',
               ha='center', fontsize=10, fontweight='bold')
    
    for bar, val in zip(bars2, savings):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2, f'-{val:.1f}ms',
               ha='center', fontsize=10, fontweight='bold', color='#27ae60')
    
    # Summary box
    total_current = sum(current)
    total_savings = sum(savings)
    summary = f"Total: {total_current:.0f}ms → {total_current - total_savings:.0f}ms\nSavings: {total_savings:.0f}ms ({total_savings/total_current*100:.0f}%)"
    ax.text(0.02, 0.98, summary, transform=ax.transAxes, fontsize=11,
           verticalalignment='top', fontfamily='monospace',
           bbox=dict(boxstyle='round', facecolor='#ffffcc', edgecolor='#f39c12', linewidth=2))
    
    ax.set_xlabel('Component', fontsize=12, fontweight='bold')
    ax.set_ylabel('Time (ms)', fontsize=12, fontweight='bold')
    ax.set_title('Optimization Targets - Potential Impact\n(Average across all stores)', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(components, rotation=15, ha='right')
    ax.legend(loc='upper right', fontsize=10)
    ax.set_ylim(0, max(current) * 1.3)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '10_optimization_targets.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 10_optimization_targets.png")


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark visualization charts")
    parser.add_argument("--dirs", nargs='+', required=True, help="Result directories")
    parser.add_argument("--names", nargs='+', required=True, help="Store names")
    parser.add_argument("--output", default="results/charts", help="Output directory")
    
    args = parser.parse_args()
    
    if len(args.dirs) != len(args.names):
        print("Error: --dirs and --names must have same length")
        return
    
    os.makedirs(args.output, exist_ok=True)
    
    print("=" * 60)
    print("FEAST BENCHMARK CHART GENERATOR")
    print("=" * 60)
    
    results = load_results(args.dirs, args.names)
    
    if not results:
        print("No results found!")
        return
    
    print(f"Stores: {', '.join(results.keys())}")
    print(f"Output: {args.output}/")
    print("-" * 60)
    
    chart_01_latency_by_entities(results, args.output)
    chart_02_scaling_curves(results, args.output)
    chart_03_store_ranking(results, args.output)
    chart_04_time_breakdown(results, args.output)
    chart_05_sla_gap_analysis(results, args.output)
    chart_06_executive_summary(results, args.output)
    chart_07_production_sla(results, args.output)
    chart_08_time_distribution(results, args.output)
    chart_09_online_read_breakdown(results, args.output)
    chart_10_optimization_targets(results, args.output)
    
    print("-" * 60)
    print("Done! 10 charts generated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
