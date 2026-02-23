"""
Benchmark Configuration - Central config for all Feast benchmarks.

This module defines the test matrix and parameters to track.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    
    # --- Test Matrix Dimensions ---
    
    # Features
    feature_counts: List[int] = field(default_factory=lambda: [50, 200])
    
    # Feature Views
    fv_counts: List[int] = field(default_factory=lambda: [1, 10, 50])
    features_per_fv: int = 10
    
    # Entities
    entity_counts: List[int] = field(default_factory=lambda: [1, 10, 50, 100, 500])
    
    # Transformations
    transformation_modes: List[str] = field(default_factory=lambda: ["none", "python", "pandas"])
    
    # Online Store (set at runtime)
    online_store: str = "sqlite"
    
    # --- Test Parameters ---
    iterations: int = 20
    warmup: int = 3
    
    # Throughput test
    throughput_workers: List[int] = field(default_factory=lambda: [1, 5, 10, 20])
    throughput_duration: int = 10  # seconds
    
    # --- SLA Targets ---
    sla_p99_ms: float = 60.0
    sla_throughput_rph: int = 3_000_000
    
    # --- Paths ---
    repo_path: str = "/tmp/feast_benchmark"
    output_dir: str = "results"


# Pre-defined configurations for different scenarios
QUICK_TEST = BenchmarkConfig(
    feature_counts=[50],
    fv_counts=[1],
    entity_counts=[1, 10, 100],
    transformation_modes=["none"],
    iterations=10,
    throughput_duration=5
)

FULL_MATRIX = BenchmarkConfig(
    feature_counts=[10, 50, 100, 200],
    fv_counts=[1, 10, 50, 100],
    entity_counts=[1, 10, 50, 100, 500],
    transformation_modes=["none", "python", "pandas"],
    iterations=20,
    throughput_workers=[1, 5, 10, 20, 50],
    throughput_duration=30
)

PRODUCTION_CONFIG = BenchmarkConfig(
    feature_counts=[200],
    fv_counts=[1, 10, 50, 100],  # Production workloads often have 100+ FVs
    entity_counts=[1, 10, 100, 500],
    transformation_modes=["none", "python", "pandas"],
    iterations=30,
    throughput_workers=[10, 50, 100],
    throughput_duration=60
)
