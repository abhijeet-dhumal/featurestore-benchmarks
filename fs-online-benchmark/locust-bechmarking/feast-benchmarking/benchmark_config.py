"""
Benchmark Configuration - Central config for all Feast benchmarks.

This module defines the test matrix and parameters to track.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs.
    
    Dimensions from TRACKER.md:
    - Features: 10, 50, 100, 200 (prod: 200)
    - Feature Views: 1, 10, 50, 100+
    - Entities: 1, 10, 50, 100, 200, 500 (State Farm: 50, 200)
    - Feature Services: 1, 5, 10
    - Transformations: None, Python, Pandas
    - Online Store: SQLite, Redis, DynamoDB, PostgreSQL
    - Region: Same-region, Cross-region
    - Compression: None, gzip
    """
    
    # --- Test Matrix Dimensions (from TRACKER.md) ---
    
    # Features: 10, 50, 100, 200 | Production target: 200
    feature_counts: List[int] = field(default_factory=lambda: [10, 50, 100, 200])
    
    # Feature Views: 1, 10, 50, 100+ | Production target: 100+
    fv_counts: List[int] = field(default_factory=lambda: [1, 10, 50, 100])
    features_per_fv: int = 10
    
    # Entities: 1, 10, 50, 100, 200, 500 | State Farm: 50, 200 | Production: 500
    entity_counts: List[int] = field(default_factory=lambda: [1, 10, 50, 100, 200, 500])
    
    # Feature Services: 1, 5, 10 | Production target: TBD
    feature_service_counts: List[int] = field(default_factory=lambda: [1, 5, 10])
    
    # Transformations: none, python, pandas | Production: both
    transformation_modes: List[str] = field(default_factory=lambda: ["none", "python", "pandas"])
    
    # Online Stores: sqlite, redis, dynamodb, postgres | Production: dynamodb
    online_stores: List[str] = field(default_factory=lambda: ["sqlite", "redis", "dynamodb", "postgres"])
    online_store: str = "sqlite"  # Current store for this run
    
    # Region Config: same-region, cross-region | Production: same
    region_configs: List[str] = field(default_factory=lambda: ["same-region", "cross-region"])
    region_config: str = "same-region"
    
    # Data Compression: none, gzip | Production: TBD
    compression_modes: List[str] = field(default_factory=lambda: ["none", "gzip"])
    compression: str = "none"
    
    # Server Type: fastapi | Production: fastapi
    server_type: str = "fastapi"
    
    # --- Test Parameters ---
    iterations: int = 20
    warmup: int = 3
    
    # Throughput test
    throughput_workers: List[int] = field(default_factory=lambda: [1, 5, 10, 20])
    throughput_duration: int = 10  # seconds
    
    # --- SLA Targets (State Farm) ---
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
    feature_service_counts=[1],
    transformation_modes=["none"],
    compression_modes=["none"],
    iterations=10,
    throughput_duration=5
)

FULL_MATRIX = BenchmarkConfig(
    # All dimensions from TRACKER.md
    feature_counts=[10, 50, 100, 200],
    fv_counts=[1, 10, 50, 100],
    entity_counts=[1, 10, 50, 100, 200, 500],
    feature_service_counts=[1, 5, 10],
    transformation_modes=["none", "python", "pandas"],
    online_stores=["sqlite", "redis", "dynamodb", "postgres"],
    region_configs=["same-region", "cross-region"],
    compression_modes=["none", "gzip"],
    iterations=20,
    throughput_workers=[1, 5, 10, 20, 50],
    throughput_duration=30
)

PRODUCTION_CONFIG = BenchmarkConfig(
    # Production-like config matching TRACKER.md targets
    feature_counts=[200],  # Production target
    fv_counts=[1, 10, 50, 100],  # 100+ FVs
    entity_counts=[1, 10, 50, 100, 200, 500],  # Includes State Farm 50, 200
    feature_service_counts=[1, 5, 10],
    transformation_modes=["none", "python", "pandas"],
    online_stores=["dynamodb"],  # Production target
    region_configs=["same-region"],  # Production target
    compression_modes=["none"],
    iterations=30,
    throughput_workers=[10, 50, 100],
    throughput_duration=60
)

# State Farm's exact SLA requirements
# 60ms p99 latency, 3M transactions/hour
# Test with 50 and 200 entities, 200 features
STATEFARM_CONFIG = BenchmarkConfig(
    feature_counts=[200],  # State Farm: 200 features
    fv_counts=[1],  # Single feature service
    entity_counts=[50, 200],  # State Farm: exact entity counts
    feature_service_counts=[1],
    transformation_modes=["none"],  # No ODFV for baseline
    online_stores=["dynamodb", "redis", "postgres"],  # Test all viable stores
    region_configs=["same-region"],
    compression_modes=["none"],
    iterations=50,  # More iterations for stable p99
    warmup=10,
    throughput_workers=[10, 20, 50],
    throughput_duration=60,
    sla_p99_ms=60.0,  # State Farm: 60ms SLA
    sla_throughput_rph=3_000_000  # State Farm: 3M/hour
)

# Cross-region latency test (DynamoDB specific)
CROSS_REGION_CONFIG = BenchmarkConfig(
    feature_counts=[200],
    fv_counts=[1],
    entity_counts=[1, 10, 50, 100],
    feature_service_counts=[1],
    transformation_modes=["none"],
    online_stores=["dynamodb"],
    region_configs=["same-region", "cross-region"],
    compression_modes=["none"],
    iterations=30,
    throughput_workers=[10, 20],
    throughput_duration=30
)

# Compression impact test
COMPRESSION_CONFIG = BenchmarkConfig(
    feature_counts=[200],
    fv_counts=[1],
    entity_counts=[50, 200, 500],  # Larger payloads benefit more
    feature_service_counts=[1],
    transformation_modes=["none"],
    online_stores=["redis"],
    compression_modes=["none", "gzip"],
    iterations=30,
    throughput_duration=30
)
