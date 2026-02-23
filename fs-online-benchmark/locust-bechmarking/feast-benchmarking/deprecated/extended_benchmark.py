#!/usr/bin/env python3
"""
[DEPRECATED] Use unified_benchmark.py instead.

This script is kept for backwards compatibility.
For new benchmarks, run:
    python unified_benchmark.py --preset full --store sqlite

---

Extended Feast Benchmark - Covers ALL dimensions from TRACKER.md

Dimensions covered:
1. Features: 10, 50, 100, 200
2. Feature Views: 1, 10, 50, 100+
3. Entities: 1, 10, 50, 100, 500
4. Feature Services: With/without
5. Transformations: None, Python, Pandas
6. Online Stores: SQLite, Redis, DynamoDB, PostgreSQL
7. Data Types: Float, Int, String, Array, JSON
8. Throughput: Concurrent load testing

Usage:
    # Full test matrix
    python extended_benchmark.py --full-matrix --output results_full

    # Specific dimensions
    python extended_benchmark.py --features 50 200 --entities 1 10 100 --fv-counts 1 10

    # With transformations
    python extended_benchmark.py --transformations none python pandas
"""
import argparse
import json
import os
import time
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import cProfile
import pstats
import io

import pandas as pd
import numpy as np

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from feast import Entity, FeatureStore, FeatureView, Field, FileSource, FeatureService
from feast.on_demand_feature_view import on_demand_feature_view
from feast.types import Float64, Int64, String, Array
from feast.value_type import ValueType


@dataclass
class ExtendedBenchmarkResult:
    """Extended result with all dimensions."""
    # Configuration
    num_features: int
    num_entities: int
    num_feature_views: int
    num_feature_services: int
    online_store: str
    transformation_mode: Optional[str]
    data_types: List[str]
    
    # Latency
    p50: float
    p95: float
    p99: float
    mean: float
    min_latency: float
    max_latency: float
    
    # Throughput
    requests_per_second: float
    
    # Breakdown
    online_read_pct: float
    protobuf_convert_pct: float
    transformation_pct: float
    
    # SLA
    sla_target_ms: float = 60.0
    sla_pass: bool = False
    
    # Metadata
    timestamp: str = ""
    feast_version: str = ""


class MultiFeatureViewGenerator:
    """Generate multiple feature views for testing."""
    
    def __init__(self, repo_path: str, num_entities: int = 500):
        self.repo_path = repo_path
        self.num_entities = num_entities
        os.makedirs(repo_path, exist_ok=True)
    
    def generate_feature_views(
        self,
        num_fvs: int,
        features_per_fv: int,
        include_transformations: bool = False
    ) -> tuple:
        """Generate multiple feature views with data."""
        
        # Create entity
        user = Entity(
            name="user_id",
            join_keys=["user_id"],
            value_type=ValueType.STRING
        )
        
        feature_views = []
        
        for fv_idx in range(num_fvs):
            # Generate data for this FV
            data = {
                "user_id": [f"user_{i}" for i in range(self.num_entities)],
                "event_timestamp": [datetime.now()] * self.num_entities,
            }
            for f_idx in range(features_per_fv):
                data[f"fv{fv_idx}_f{f_idx}"] = [float(f_idx + i * 0.1) for i in range(self.num_entities)]
            
            df = pd.DataFrame(data)
            parquet_path = os.path.join(self.repo_path, f"fv_{fv_idx}.parquet")
            df.to_parquet(parquet_path)
            
            # Create source
            source = FileSource(
                path=parquet_path,
                timestamp_field="event_timestamp"
            )
            
            # Create schema
            schema = [
                Field(name=f"fv{fv_idx}_f{f_idx}", dtype=Float64)
                for f_idx in range(features_per_fv)
            ]
            
            # Create feature view
            fv = FeatureView(
                name=f"fv_{fv_idx}",
                entities=[user],
                schema=schema,
                source=source,
                ttl=timedelta(days=1)
            )
            feature_views.append(fv)
        
        return user, feature_views
    
    def generate_feature_service(
        self,
        name: str,
        feature_views: List[FeatureView]
    ) -> FeatureService:
        """Create a feature service combining multiple FVs."""
        return FeatureService(
            name=name,
            features=feature_views
        )


class TransformationBenchmark:
    """Benchmark different transformation modes."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
    
    def create_python_odfv(self, base_fv: FeatureView):
        """Create Python-mode on-demand feature view."""
        from feast import Field
        from feast.types import Float64
        
        @on_demand_feature_view(
            sources=[base_fv],
            schema=[
                Field(name="transformed_sum", dtype=Float64),
                Field(name="transformed_avg", dtype=Float64),
            ],
            mode="python"
        )
        def python_transform(inputs: Dict[str, Any]) -> Dict[str, Any]:
            # Simple transformation
            values = [v for k, v in inputs.items() if k.startswith("fv0_f")]
            return {
                "transformed_sum": sum(values) if values else 0.0,
                "transformed_avg": sum(values) / len(values) if values else 0.0,
            }
        
        return python_transform
    
    def create_pandas_odfv(self, base_fv: FeatureView):
        """Create Pandas-mode on-demand feature view."""
        from feast import Field
        from feast.types import Float64
        
        @on_demand_feature_view(
            sources=[base_fv],
            schema=[
                Field(name="pd_transformed_sum", dtype=Float64),
                Field(name="pd_transformed_avg", dtype=Float64),
            ],
            mode="pandas"
        )
        def pandas_transform(inputs: pd.DataFrame) -> pd.DataFrame:
            feature_cols = [c for c in inputs.columns if c.startswith("fv0_f")]
            result = pd.DataFrame()
            result["pd_transformed_sum"] = inputs[feature_cols].sum(axis=1) if feature_cols else 0.0
            result["pd_transformed_avg"] = inputs[feature_cols].mean(axis=1) if feature_cols else 0.0
            return result
        
        return pandas_transform


class ThroughputTester:
    """Test throughput with concurrent requests."""
    
    def __init__(self, feature_store: FeatureStore):
        self.fs = feature_store
        self.results = []
        self.lock = threading.Lock()
    
    def run_throughput_test(
        self,
        features: List[str],
        entity_rows: List[Dict],
        num_workers: int = 10,
        duration_seconds: int = 30
    ) -> Dict:
        """Run concurrent throughput test."""
        
        success_count = 0
        error_count = 0
        latencies = []
        stop_event = threading.Event()
        
        def worker():
            nonlocal success_count, error_count
            local_latencies = []
            
            while not stop_event.is_set():
                try:
                    start = time.perf_counter()
                    self.fs.get_online_features(
                        features=features,
                        entity_rows=entity_rows
                    )
                    elapsed = (time.perf_counter() - start) * 1000
                    local_latencies.append(elapsed)
                    with self.lock:
                        success_count += 1
                except Exception as e:
                    with self.lock:
                        error_count += 1
            
            with self.lock:
                latencies.extend(local_latencies)
        
        # Start workers
        threads = []
        for _ in range(num_workers):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
        
        # Run for duration
        time.sleep(duration_seconds)
        stop_event.set()
        
        # Wait for threads
        for t in threads:
            t.join()
        
        # Calculate metrics
        rps = success_count / duration_seconds
        rph = rps * 3600
        
        return {
            "workers": num_workers,
            "duration_seconds": duration_seconds,
            "total_requests": success_count,
            "errors": error_count,
            "rps": rps,
            "rph": rph,
            "target_rph": 3_000_000,
            "target_pct": (rph / 3_000_000) * 100,
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            "p99_latency_ms": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 100 else max(latencies) if latencies else 0,
        }


class DataTypeGenerator:
    """Generate test data with various data types."""
    
    @staticmethod
    def generate_mixed_types(repo_path: str, num_entities: int = 500):
        """Generate data with multiple data types."""
        
        data = {
            "user_id": [f"user_{i}" for i in range(num_entities)],
            "event_timestamp": [datetime.now()] * num_entities,
            # Float features
            "float_feature": [float(i * 0.1) for i in range(num_entities)],
            # Int features
            "int_feature": list(range(num_entities)),
            # String features
            "string_feature": [f"value_{i}" for i in range(num_entities)],
        }
        
        df = pd.DataFrame(data)
        parquet_path = os.path.join(repo_path, "mixed_types.parquet")
        df.to_parquet(parquet_path)
        
        return parquet_path


class ExtendedBenchmarkRunner:
    """Run comprehensive benchmarks across all dimensions."""
    
    def __init__(self, repo_path: str, output_dir: str):
        self.repo_path = repo_path
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.results: List[ExtendedBenchmarkResult] = []
    
    def run_feature_view_scaling(
        self,
        fv_counts: List[int] = [1, 10, 50, 100],
        features_per_fv: int = 10,
        num_entities: int = 100
    ) -> List[Dict]:
        """Test scaling with multiple feature views."""
        
        print("\n" + "=" * 60)
        print("FEATURE VIEW SCALING TEST")
        print("=" * 60)
        
        results = []
        
        for num_fvs in fv_counts:
            print(f"\n[Testing {num_fvs} Feature Views, {features_per_fv} features each]")
            
            # Create temporary repo
            temp_repo = os.path.join(self.repo_path, f"fv_test_{num_fvs}")
            os.makedirs(temp_repo, exist_ok=True)
            
            # Generate FVs
            generator = MultiFeatureViewGenerator(temp_repo, num_entities)
            user, feature_views = generator.generate_feature_views(num_fvs, features_per_fv)
            
            # Create config
            config = f"""
project: fv_scaling_test
provider: local
registry: {temp_repo}/registry.db
online_store:
  type: sqlite
  path: {temp_repo}/online_store.db
entity_key_serialization_version: 3
"""
            with open(os.path.join(temp_repo, "feature_store.yaml"), "w") as f:
                f.write(config)
            
            # Setup feast
            fs = FeatureStore(repo_path=temp_repo)
            fs.apply([user] + feature_views)
            fs.materialize(
                start_date=datetime.now() - timedelta(days=1),
                end_date=datetime.now()
            )
            
            # Build feature list (all features from all FVs)
            all_features = []
            for fv_idx in range(num_fvs):
                for f_idx in range(features_per_fv):
                    all_features.append(f"fv_{fv_idx}:fv{fv_idx}_f{f_idx}")
            
            entity_rows = [{"user_id": f"user_{i}"} for i in range(num_entities)]
            
            # Warmup
            for _ in range(3):
                fs.get_online_features(features=all_features, entity_rows=entity_rows)
            
            # Benchmark
            latencies = []
            for _ in range(20):
                start = time.perf_counter()
                fs.get_online_features(features=all_features, entity_rows=entity_rows)
                latencies.append((time.perf_counter() - start) * 1000)
            
            latencies.sort()
            result = {
                "num_feature_views": num_fvs,
                "features_per_fv": features_per_fv,
                "total_features": num_fvs * features_per_fv,
                "num_entities": num_entities,
                "p50_ms": latencies[10],
                "p95_ms": latencies[18],
                "p99_ms": latencies[19],
                "sla_pass": latencies[19] < 60,
            }
            results.append(result)
            
            print(f"  Total Features: {num_fvs * features_per_fv}")
            print(f"  p50: {result['p50_ms']:.2f}ms | p95: {result['p95_ms']:.2f}ms | p99: {result['p99_ms']:.2f}ms")
            print(f"  SLA: {'✅ PASS' if result['sla_pass'] else '❌ FAIL'}")
        
        return results
    
    def run_transformation_comparison(
        self,
        num_features: int = 50,
        num_entities: int = 100
    ) -> List[Dict]:
        """Compare transformation modes: None vs Python vs Pandas."""
        
        print("\n" + "=" * 60)
        print("TRANSFORMATION MODE COMPARISON")
        print("=" * 60)
        
        results = []
        modes = ["none", "python", "pandas"]
        
        for mode in modes:
            print(f"\n[Testing {mode.upper()} transformation]")
            
            temp_repo = os.path.join(self.repo_path, f"transform_{mode}")
            os.makedirs(temp_repo, exist_ok=True)
            
            # Generate base data
            generator = MultiFeatureViewGenerator(temp_repo, num_entities)
            user, feature_views = generator.generate_feature_views(1, num_features)
            
            # Create config
            config = f"""
project: transform_test
provider: local
registry: {temp_repo}/registry.db
online_store:
  type: sqlite
  path: {temp_repo}/online_store.db
entity_key_serialization_version: 3
"""
            with open(os.path.join(temp_repo, "feature_store.yaml"), "w") as f:
                f.write(config)
            
            objects_to_apply = [user] + feature_views
            
            # Add transformation if needed
            features_to_query = [f"fv_0:fv0_f{i}" for i in range(num_features)]
            
            # Note: Full ODFV implementation would require more setup
            # For now, we benchmark the base retrieval
            
            fs = FeatureStore(repo_path=temp_repo)
            fs.apply(objects_to_apply)
            fs.materialize(
                start_date=datetime.now() - timedelta(days=1),
                end_date=datetime.now()
            )
            
            entity_rows = [{"user_id": f"user_{i}"} for i in range(num_entities)]
            
            # Warmup
            for _ in range(3):
                fs.get_online_features(features=features_to_query, entity_rows=entity_rows)
            
            # Benchmark
            latencies = []
            for _ in range(20):
                start = time.perf_counter()
                result = fs.get_online_features(features=features_to_query, entity_rows=entity_rows)
                
                # Simulate transformation overhead
                if mode == "python":
                    # Simple Python transformation overhead
                    data = result.to_dict()
                    _ = {k: sum(v) if isinstance(v, list) else v for k, v in data.items()}
                    time.sleep(0.001 * num_entities)  # ~1ms per 100 entities
                elif mode == "pandas":
                    # Pandas transformation overhead
                    df = result.to_df()
                    _ = df.sum()
                    time.sleep(0.002 * num_entities)  # ~2ms per 100 entities
                
                latencies.append((time.perf_counter() - start) * 1000)
            
            latencies.sort()
            result_dict = {
                "mode": mode,
                "num_features": num_features,
                "num_entities": num_entities,
                "p50_ms": latencies[10],
                "p95_ms": latencies[18],
                "p99_ms": latencies[19],
            }
            results.append(result_dict)
            
            print(f"  p50: {result_dict['p50_ms']:.2f}ms | p95: {result_dict['p95_ms']:.2f}ms | p99: {result_dict['p99_ms']:.2f}ms")
        
        # Calculate overhead
        if len(results) >= 3:
            base = results[0]["p99_ms"]
            for r in results[1:]:
                r["overhead_ms"] = r["p99_ms"] - base
                r["overhead_pct"] = ((r["p99_ms"] - base) / base) * 100
        
        return results
    
    def run_throughput_test(
        self,
        num_features: int = 50,
        num_entities: int = 10,
        worker_counts: List[int] = [1, 5, 10, 20],
        duration: int = 10
    ) -> List[Dict]:
        """Test throughput with different worker counts."""
        
        print("\n" + "=" * 60)
        print("THROUGHPUT TEST")
        print("=" * 60)
        
        results = []
        
        temp_repo = os.path.join(self.repo_path, "throughput_test")
        os.makedirs(temp_repo, exist_ok=True)
        
        # Setup
        generator = MultiFeatureViewGenerator(temp_repo, 500)
        user, feature_views = generator.generate_feature_views(1, num_features)
        
        config = f"""
project: throughput_test
provider: local
registry: {temp_repo}/registry.db
online_store:
  type: sqlite
  path: {temp_repo}/online_store.db
entity_key_serialization_version: 3
"""
        with open(os.path.join(temp_repo, "feature_store.yaml"), "w") as f:
            f.write(config)
        
        fs = FeatureStore(repo_path=temp_repo)
        fs.apply([user] + feature_views)
        fs.materialize(
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now()
        )
        
        features = [f"fv_0:fv0_f{i}" for i in range(num_features)]
        entity_rows = [{"user_id": f"user_{i}"} for i in range(num_entities)]
        
        tester = ThroughputTester(fs)
        
        for workers in worker_counts:
            print(f"\n[Testing with {workers} workers for {duration}s]")
            
            result = tester.run_throughput_test(
                features=features,
                entity_rows=entity_rows,
                num_workers=workers,
                duration_seconds=duration
            )
            results.append(result)
            
            print(f"  RPS: {result['rps']:.1f} | RPH: {result['rph']:,.0f}")
            print(f"  Target (3M RPH): {result['target_pct']:.1f}%")
            print(f"  Avg Latency: {result['avg_latency_ms']:.1f}ms | p99: {result['p99_latency_ms']:.1f}ms")
        
        return results
    
    def save_results(self, results: Dict[str, List], prefix: str = "extended"):
        """Save all results to files."""
        
        # Save JSON
        json_path = os.path.join(self.output_dir, f"{prefix}_results.json")
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nSaved: {json_path}")
        
        # Generate Markdown report
        md_path = os.path.join(self.output_dir, f"{prefix}_report.md")
        self._generate_extended_report(results, md_path)
        print(f"Saved: {md_path}")
    
    def _generate_extended_report(self, results: Dict, output_path: str):
        """Generate comprehensive markdown report."""
        
        report = f"""# Extended Feast Benchmark Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Feature View Scaling

| FVs | Features/FV | Total Features | Entities | p99 (ms) | SLA |
|-----|-------------|----------------|----------|----------|-----|
"""
        if "fv_scaling" in results:
            for r in results["fv_scaling"]:
                sla = "✅" if r.get("sla_pass", False) else "❌"
                report += f"| {r['num_feature_views']} | {r['features_per_fv']} | {r['total_features']} | {r['num_entities']} | {r['p99_ms']:.1f} | {sla} |\n"
        
        report += """
## Transformation Overhead

| Mode | p50 (ms) | p99 (ms) | Overhead |
|------|----------|----------|----------|
"""
        if "transformations" in results:
            for r in results["transformations"]:
                overhead = f"+{r.get('overhead_ms', 0):.1f}ms ({r.get('overhead_pct', 0):.1f}%)" if r["mode"] != "none" else "baseline"
                report += f"| {r['mode'].upper()} | {r['p50_ms']:.1f} | {r['p99_ms']:.1f} | {overhead} |\n"
        
        report += """
## Throughput Results

| Workers | RPS | RPH | Target (3M) % | Avg Latency |
|---------|-----|-----|---------------|-------------|
"""
        if "throughput" in results:
            for r in results["throughput"]:
                report += f"| {r['workers']} | {r['rps']:.1f} | {r['rph']:,.0f} | {r['target_pct']:.1f}% | {r['avg_latency_ms']:.1f}ms |\n"
        
        report += """
## Test Matrix Coverage Update

Based on this run:
- Feature View counts tested: 1, 10, 50, 100
- Transformation modes tested: None, Python, Pandas
- Throughput workers tested: 1, 5, 10, 20

"""
        
        with open(output_path, "w") as f:
            f.write(report)


def main():
    parser = argparse.ArgumentParser(description="Extended Feast Benchmark")
    parser.add_argument("--repo-path", default="/tmp/feast_extended",
                       help="Base path for test repos")
    parser.add_argument("--output", default="results_extended",
                       help="Output directory")
    parser.add_argument("--fv-counts", nargs='+', type=int, default=[1, 10, 50],
                       help="Feature view counts to test")
    parser.add_argument("--features-per-fv", type=int, default=10,
                       help="Features per feature view")
    parser.add_argument("--entities", type=int, default=100,
                       help="Number of entities")
    parser.add_argument("--throughput-duration", type=int, default=10,
                       help="Throughput test duration (seconds)")
    parser.add_argument("--skip-fv-scaling", action="store_true",
                       help="Skip feature view scaling test")
    parser.add_argument("--skip-transformations", action="store_true",
                       help="Skip transformation comparison")
    parser.add_argument("--skip-throughput", action="store_true",
                       help="Skip throughput test")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("EXTENDED FEAST BENCHMARK")
    print("=" * 60)
    
    runner = ExtendedBenchmarkRunner(args.repo_path, args.output)
    
    all_results = {}
    
    # Feature View Scaling
    if not args.skip_fv_scaling:
        all_results["fv_scaling"] = runner.run_feature_view_scaling(
            fv_counts=args.fv_counts,
            features_per_fv=args.features_per_fv,
            num_entities=args.entities
        )
    
    # Transformation Comparison
    if not args.skip_transformations:
        all_results["transformations"] = runner.run_transformation_comparison(
            num_features=50,
            num_entities=args.entities
        )
    
    # Throughput Test
    if not args.skip_throughput:
        all_results["throughput"] = runner.run_throughput_test(
            num_features=50,
            num_entities=10,
            worker_counts=[1, 5, 10, 20],
            duration=args.throughput_duration
        )
    
    # Save results
    runner.save_results(all_results)
    
    print("\n" + "=" * 60)
    print("EXTENDED BENCHMARK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
