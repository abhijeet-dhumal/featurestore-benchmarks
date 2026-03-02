#!/usr/bin/env python3
"""
Detailed Function-Level Profiling for Feast Online Feature Retrieval

Runs get_online_features() with cProfile and outputs a breakdown of where
time is spent at the function level. Useful for identifying optimization targets.

Usage:
    python profile_breakdown.py --entities 50 --features 200 --store sqlite
"""
import argparse
import cProfile
import pstats
import io
import os
import json
import tempfile
import time
from datetime import timedelta
from typing import Dict, List, Tuple
from collections import defaultdict

import numpy as np
import pandas as pd

from feast import Entity, FeatureStore, FeatureView, Field, FileSource
from feast.types import Float64
from feast.value_type import ValueType


def create_test_repo(repo_path: str, num_features: int, num_entities: int) -> str:
    """Create a minimal Feast repo for profiling."""
    os.makedirs(repo_path, exist_ok=True)
    
    # Create feature_store.yaml
    config = f"""
project: profiling_test
registry: {repo_path}/registry.db
provider: local
online_store:
  type: sqlite
  path: {repo_path}/online_store.db
entity_key_serialization_version: 3
"""
    with open(os.path.join(repo_path, "feature_store.yaml"), "w") as f:
        f.write(config)
    
    # Create test data
    data = {"user_id": [f"user_{i}" for i in range(num_entities)],
            "event_timestamp": [pd.Timestamp.now()] * num_entities}
    for i in range(num_features):
        data[f"feature_{i}"] = np.random.randn(num_entities)
    
    df = pd.DataFrame(data)
    parquet_path = os.path.join(repo_path, "data.parquet")
    df.to_parquet(parquet_path)
    
    # Create entity and feature view
    user = Entity(name="user_id", join_keys=["user_id"], value_type=ValueType.STRING)
    
    source = FileSource(path=parquet_path, timestamp_field="event_timestamp")
    schema = [Field(name=f"feature_{i}", dtype=Float64) for i in range(num_features)]
    
    fv = FeatureView(
        name="test_features",
        entities=[user],
        schema=schema,
        source=source,
        ttl=timedelta(days=1)
    )
    
    # Apply and materialize
    fs = FeatureStore(repo_path=repo_path)
    fs.apply([user, fv])
    fs.materialize_incremental(end_date=pd.Timestamp.now())
    
    return repo_path


def profile_request(fs: FeatureStore, features: List[str], entity_rows: List[Dict], 
                    iterations: int = 10) -> Tuple[Dict, float]:
    """Profile get_online_features() and return function-level breakdown."""
    
    profiler = cProfile.Profile()
    
    # Warmup
    for _ in range(3):
        fs.get_online_features(features=features, entity_rows=entity_rows)
    
    # Profile multiple iterations
    start = time.perf_counter()
    profiler.enable()
    for _ in range(iterations):
        fs.get_online_features(features=features, entity_rows=entity_rows)
    profiler.disable()
    total_time = (time.perf_counter() - start) * 1000  # ms
    avg_time = total_time / iterations
    
    # Parse profiler stats
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    
    # Get function-level breakdown
    function_times = defaultdict(float)
    
    for (filename, lineno, funcname), (cc, nc, tt, ct, callers) in stats.stats.items():
        # ct = cumulative time, tt = total time (just this function)
        # We want tt (time spent IN this function, not including subcalls)
        time_ms = tt * 1000 / iterations  # Average per iteration in ms
        
        # Group by meaningful function names
        if time_ms > 0.1:  # Only include functions taking > 0.1ms
            # Clean up function name
            if 'feast' in filename.lower() or funcname in [
                'get_online_features', 'online_read', '_get_online_features',
                'serialize_entity_key', '_convert_rows_to_protobuf', 'MessageToDict',
                'read', 'execute', 'fetchall', 'mget', 'pipeline'
            ]:
                key = f"{funcname}"
                if 'feast' in filename.lower():
                    # Extract module name
                    parts = filename.split('/')
                    for i, p in enumerate(parts):
                        if p == 'feast' and i + 1 < len(parts):
                            module = parts[i + 1].replace('.py', '')
                            key = f"{module}.{funcname}"
                            break
                function_times[key] += time_ms
    
    return dict(function_times), avg_time


def run_detailed_profile(store_type: str, num_entities: int, num_features: int, 
                         iterations: int = 10) -> Dict:
    """Run detailed profiling and return results."""
    
    print(f"\n{'='*70}")
    print(f"DETAILED FUNCTION PROFILING")
    print(f"Store: {store_type} | Entities: {num_entities} | Features: {num_features}")
    print(f"{'='*70}\n")
    
    # Create test repo
    with tempfile.TemporaryDirectory() as repo_path:
        print(f"Creating test repo...")
        create_test_repo(repo_path, num_features, num_entities)
        
        fs = FeatureStore(repo_path=repo_path)
        fs.refresh_registry()
        
        features = [f"test_features:feature_{i}" for i in range(num_features)]
        entity_rows = [{"user_id": f"user_{i}"} for i in range(num_entities)]
        
        print(f"Running {iterations} iterations with profiling...\n")
        
        function_times, avg_total = profile_request(fs, features, entity_rows, iterations)
    
    # Sort by time (descending)
    sorted_times = sorted(function_times.items(), key=lambda x: x[1], reverse=True)
    
    # Print results
    print(f"{'Function':<50} {'Time (ms)':>12} {'% of Total':>12}")
    print("-" * 74)
    
    for func, time_ms in sorted_times[:25]:  # Top 25 functions
        pct = (time_ms / avg_total) * 100 if avg_total > 0 else 0
        print(f"{func:<50} {time_ms:>10.2f}ms {pct:>10.1f}%")
    
    print("-" * 74)
    print(f"{'TOTAL (avg per request)':<50} {avg_total:>10.2f}ms {100.0:>10.1f}%")
    
    # Group by category
    print(f"\n{'='*70}")
    print("GROUPED BY CATEGORY")
    print(f"{'='*70}\n")
    
    categories = {
        'Serialization/Protobuf': ['MessageToDict', 'protobuf', 'serialize', '_convert'],
        'Online Store Read': ['online_read', 'read', 'execute', 'fetchall', 'mget', 'pipeline', 'redis', 'sqlite', 'dynamodb'],
        'Entity Key Handling': ['entity_key', 'serialize_entity_key', 'EntityKeyProto'],
        'Registry/Metadata': ['registry', 'get_entity', 'get_feature_view', 'feature_service'],
        'Request Preparation': ['prepare', 'request', 'context'],
    }
    
    category_times = defaultdict(float)
    categorized = set()
    
    for func, time_ms in sorted_times:
        for category, keywords in categories.items():
            if any(kw.lower() in func.lower() for kw in keywords):
                category_times[category] += time_ms
                categorized.add(func)
                break
    
    # Add uncategorized
    for func, time_ms in sorted_times:
        if func not in categorized:
            category_times['Other'] += time_ms
    
    sorted_categories = sorted(category_times.items(), key=lambda x: x[1], reverse=True)
    
    print(f"{'Category':<40} {'Time (ms)':>12} {'% of Total':>12}")
    print("-" * 64)
    
    for category, time_ms in sorted_categories:
        pct = (time_ms / avg_total) * 100 if avg_total > 0 else 0
        print(f"{category:<40} {time_ms:>10.2f}ms {pct:>10.1f}%")
    
    print("-" * 64)
    print(f"{'TOTAL':<40} {avg_total:>10.2f}ms {100.0:>10.1f}%")
    
    # Return structured results
    return {
        'config': {
            'store': store_type,
            'entities': num_entities,
            'features': num_features,
            'iterations': iterations
        },
        'total_ms': avg_total,
        'function_breakdown': dict(sorted_times[:25]),
        'category_breakdown': dict(sorted_categories)
    }


def main():
    parser = argparse.ArgumentParser(description="Profile Feast get_online_features() at function level")
    parser.add_argument("--store", default="sqlite", choices=["sqlite", "redis", "postgres", "dynamodb"],
                        help="Online store type (default: sqlite)")
    parser.add_argument("--entities", type=int, default=50, help="Number of entities (default: 50)")
    parser.add_argument("--features", type=int, default=200, help="Number of features (default: 200)")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations to average (default: 10)")
    parser.add_argument("--output", help="Output JSON file for results")
    
    args = parser.parse_args()
    
    results = run_detailed_profile(
        store_type=args.store,
        num_entities=args.entities,
        num_features=args.features,
        iterations=args.iterations
    )
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total latency: {results['total_ms']:.2f}ms for {args.entities} entities, {args.features} features")
    print(f"\nTop 3 categories:")
    for i, (cat, time_ms) in enumerate(list(results['category_breakdown'].items())[:3]):
        pct = (time_ms / results['total_ms']) * 100
        print(f"  {i+1}. {cat}: {time_ms:.2f}ms ({pct:.1f}%)")


if __name__ == "__main__":
    main()
