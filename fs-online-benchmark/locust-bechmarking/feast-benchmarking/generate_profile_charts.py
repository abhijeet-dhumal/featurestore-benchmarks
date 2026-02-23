#!/usr/bin/env python3
"""
Profile Chart Generator - Visualizes function-level breakdown.

Output:
  05_high_level_breakdown.png   - Time spent in each Feast component
  06_online_read_breakdown.png  - Store-specific internals
  07_optimization_targets.png   - Where to focus optimization efforts
"""
import argparse
import json
import os

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid')

COLORS = {
    'sqlite': '#2ecc71',
    'redis': '#e74c3c',
    'postgres': '#3498db',
    'dynamodb': '#f39c12',
}

COMPONENT_COLORS = {
    'proto_convert': '#e74c3c',
    'online_read': '#3498db',
    'prepare_entities': '#f39c12',
    'request_context': '#9b59b6',
    'serialize_entity_key': '#1abc9c',
    'other': '#95a5a6',
}


def load_profile_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def chart_high_level_breakdown(data: dict, output_dir: str):
    """05 - Stacked bar showing time breakdown by component."""
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Handle both 'results' and 'stores' keys
    results = data.get('stores', data.get('results', {}))
    stores = [s for s in results.keys() if 'error' not in results[s]]
    
    # Map from actual data keys to display components
    key_mapping = {
        'protobuf_convert': 'proto_convert',
        'online_read': 'online_read',
        '_prepare_entities': 'prepare_entities',
        '_get_online_request_context': 'request_context',
        'serialize_entity_key': 'serialize_entity_key',
    }
    components = ['proto_convert', 'online_read', 'prepare_entities', 'request_context', 'serialize_entity_key']
    
    x = np.arange(len(stores))
    width = 0.6
    
    bottom = np.zeros(len(stores))
    
    for comp in components:
        values = []
        for store in stores:
            # Try both formats: nested 'high_level' or flat 'breakdown'
            store_data = results[store]
            if 'high_level' in store_data:
                val = store_data['high_level'].get(comp, 0)
            elif 'breakdown' in store_data:
                # Find the matching key from breakdown
                val = 0
                for orig_key, mapped_key in key_mapping.items():
                    if mapped_key == comp:
                        val = store_data['breakdown'].get(orig_key, 0)
                        break
            else:
                val = 0
            values.append(val)
        
        bars = ax.bar(x, values, width, bottom=bottom, 
                     label=comp.replace('_', ' ').title(),
                     color=COMPONENT_COLORS.get(comp, '#95a5a6'),
                     edgecolor='white', linewidth=1)
        
        # Add value labels for significant components
        for i, (val, b) in enumerate(zip(values, bottom)):
            if val > 2:
                ax.text(i, b + val/2, f'{val:.1f}ms', 
                       ha='center', va='center', fontsize=9, fontweight='bold', color='white')
        
        bottom += np.array(values)
    
    # Add total labels on top
    for i, store in enumerate(stores):
        store_data = results[store]
        total = store_data.get('latency', {}).get('mean', store_data.get('avg_ms', 0))
        ax.text(i, bottom[i] + 2, f'{total:.1f}ms', 
               ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_xlabel('Online Store', fontsize=13, fontweight='bold')
    ax.set_ylabel('Time (ms)', fontsize=13, fontweight='bold')
    ax.set_title('Request Time Breakdown by Component\n(100 entities, 50 features)', 
                fontsize=15, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels([s.upper() for s in stores], fontsize=12)
    ax.legend(loc='upper right', fontsize=10)
    ax.set_ylim(0, max(bottom) * 1.15)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '05_high_level_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 05_high_level_breakdown.png")


def chart_online_read_breakdown(data: dict, output_dir: str):
    """06 - Horizontal bar chart showing online_read internals per store."""
    results = data.get('stores', data.get('results', {}))
    stores = [s for s in results.keys() if 'error' not in results[s]]
    
    n_stores = len(stores)
    cols = min(2, n_stores)
    rows = (n_stores + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(8*cols, 6*rows))
    if n_stores == 1:
        axes = [axes]
    else:
        axes = axes.flatten() if hasattr(axes, 'flatten') else [axes]
    
    for idx, store in enumerate(stores):
        ax = axes[idx] if idx < len(axes) else axes[-1]
        breakdown = results[store].get('online_read_breakdown', {})
        
        # Filter to top components
        sorted_items = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:8]
        
        if not sorted_items:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f'{store.upper()}', fontsize=14, fontweight='bold')
            continue
        
        labels = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]
        
        y_pos = np.arange(len(labels))
        
        bars = ax.barh(y_pos, values, color=COLORS.get(store, '#95a5a6'), alpha=0.8, edgecolor='white')
        
        # Add value labels
        for bar, val in zip(bars, values):
            ax.text(val + max(values)*0.02, bar.get_y() + bar.get_height()/2,
                   f'{val:.1f}ms', va='center', fontsize=9)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=10)
        ax.set_xlabel('Cumulative Time (ms)', fontsize=11)
        ax.set_title(f'{store.upper()} - online_read() Internals', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        ax.set_xlim(0, max(values) * 1.25)
    
    plt.suptitle('online_read() Function Breakdown by Store\n(100 entities, 50 features, 10 iterations cumulative)',
                fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '06_online_read_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 06_online_read_breakdown.png")


def chart_optimization_targets(data: dict, output_dir: str):
    """07 - Waterfall chart showing optimization opportunities."""
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Aggregate data across stores
    results = data.get('stores', data.get('results', {}))
    stores = [s for s in results.keys() if 'error' not in results[s]]
    
    # Calculate average breakdown
    components = {}
    for store in stores:
        store_data = results[store]
        # Try high_level first, then breakdown
        hl = store_data.get('high_level', store_data.get('breakdown', {}))
        for comp, val in hl.items():
            if comp not in ('total_get_online_features', 'get_online_features'):
                if comp not in components:
                    components[comp] = []
                components[comp].append(val)
    
    avg_components = {k: np.mean(v) for k, v in components.items()}
    
    # Sort by impact
    sorted_comps = sorted(avg_components.items(), key=lambda x: x[1], reverse=True)
    
    labels = [item[0].replace('_', ' ').title() for item in sorted_comps]
    values = [item[1] for item in sorted_comps]
    
    # Calculate potential savings (assume 50% optimization possible)
    savings = [v * 0.5 for v in values]
    
    x = np.arange(len(labels))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, values, width, label='Current Time', color='#e74c3c', alpha=0.8)
    bars2 = ax.bar(x + width/2, savings, width, label='Potential Savings (50%)', color='#2ecc71', alpha=0.8)
    
    # Add value labels
    for bar, val in zip(bars1, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
               f'{val:.1f}ms', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    for bar, val in zip(bars2, savings):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
               f'-{val:.1f}ms', ha='center', va='bottom', fontsize=9, color='green', fontweight='bold')
    
    ax.set_xlabel('Component', fontsize=13, fontweight='bold')
    ax.set_ylabel('Time (ms)', fontsize=13, fontweight='bold')
    ax.set_title('Optimization Targets - Potential Impact\n(Average across all stores)',
                fontsize=15, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10, rotation=25, ha='right')
    ax.set_ylim(0, max(values) * 1.4)
    
    # Add annotation box (moved to left side to avoid legend overlap)
    total_current = sum(values)
    total_savings = sum(savings)
    ax.annotate(f'Total: {total_current:.0f}ms → {total_current-total_savings:.0f}ms\nSavings: {total_savings:.0f}ms ({total_savings/total_current*100:.0f}%)',
               xy=(0.02, 0.98), xycoords='axes fraction',
               fontsize=10, ha='left', va='top',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', edgecolor='orange'))
    
    # Legend below annotation
    ax.legend(loc='upper left', fontsize=10, bbox_to_anchor=(0.02, 0.82))
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '07_optimization_targets.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 07_optimization_targets.png")


def chart_store_comparison_pie(data: dict, output_dir: str):
    """08 - Pie charts showing time distribution per store."""
    results = data.get('stores', data.get('results', {}))
    stores = [s for s in results.keys() if 'error' not in results[s]]
    
    n_stores = len(stores)
    # Use 1 row for 3 or fewer stores, 2 rows for more
    if n_stores <= 3:
        fig, axes = plt.subplots(1, n_stores, figsize=(6*n_stores, 6))
    else:
        cols = 2
        rows = (n_stores + 1) // 2
        fig, axes = plt.subplots(rows, cols, figsize=(12, 6*rows))
    
    if n_stores == 1:
        axes = [axes]
    else:
        axes = axes.flatten() if hasattr(axes, 'flatten') else list(axes)
    
    # Hide unused axes
    for i in range(n_stores, len(axes)):
        axes[i].set_visible(False)
    
    for idx, store in enumerate(stores):
        ax = axes[idx]
        store_data = results[store]
        hl = store_data.get('high_level', store_data.get('breakdown', {}))
        
        # Filter components and sort by value
        components = {k: v for k, v in hl.items() if k not in ('total_get_online_features', 'get_online_features') and v > 0}
        
        if not components:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', fontsize=12)
            ax.set_title(f'{store.upper()}', fontsize=14, fontweight='bold')
            continue
        
        # Sort by value descending
        sorted_items = sorted(components.items(), key=lambda x: x[1], reverse=True)
        comp_keys = [item[0] for item in sorted_items]
        sizes = [item[1] for item in sorted_items]
        colors = [COMPONENT_COLORS.get(k, '#95a5a6') for k in comp_keys]
        
        # Create pie without labels, use legend instead
        wedges, texts, autotexts = ax.pie(sizes, colors=colors, autopct='%1.0f%%',
                                          startangle=90, pctdistance=0.8,
                                          wedgeprops=dict(width=0.5, edgecolor='white'))
        
        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
            autotext.set_color('white')
        
        # Add legend
        legend_labels = [k.replace('_', ' ').title() for k in comp_keys]
        ax.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1, 0.5), fontsize=9)
        
        total = store_data.get('latency', {}).get('mean', store_data.get('avg_ms', sum(sizes)))
        ax.set_title(f'{store.upper()}\nTotal: {total:.1f}ms', fontsize=14, fontweight='bold')
    
    plt.suptitle('Time Distribution by Component\n(100 entities, 50 features)',
                fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '08_time_distribution.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: 08_time_distribution.png")


def main():
    parser = argparse.ArgumentParser(description="Generate profiling breakdown charts")
    parser.add_argument("--input", default="results/profile/deep_profile_results.json",
                       help="Path to profile results JSON")
    parser.add_argument("--output", default="results/comparison",
                       help="Output directory for charts")
    
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    print("=" * 60)
    print("PROFILE CHART GENERATOR")
    print("=" * 60)
    
    data = load_profile_results(args.input)
    
    print(f"Input: {args.input}")
    print(f"Output: {args.output}/")
    print("-" * 60)
    
    chart_high_level_breakdown(data, args.output)
    chart_online_read_breakdown(data, args.output)
    chart_optimization_targets(data, args.output)
    chart_store_comparison_pie(data, args.output)
    
    print("-" * 60)
    print("Done! 4 profile charts generated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
