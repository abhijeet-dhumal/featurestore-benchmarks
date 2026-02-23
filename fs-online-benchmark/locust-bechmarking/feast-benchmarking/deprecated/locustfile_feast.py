"""
Feast Online Feature Store Benchmark using Locust.

This benchmark follows the featurestore-benchmarks methodology for fair comparison
with other feature stores (Hopsworks, Vertex, SageMaker).

Usage:
    # Single user test
    python locustfile_feast.py

    # Distributed load test
    locust -f locustfile_feast.py --host=http://localhost

    # Docker distributed mode
    docker-compose -f docker-compose-feast.yml up --scale worker=32
"""
import random
import json
import os
from typing import List, Dict, Any

from locust import User, constant, task, events, run_single_user
from locust.runners import MasterRunner
import numpy as np

from common.stop_watch import stopwatch
from feast import FeatureStore


# Global feature store instance (initialized per worker)
_feature_store: FeatureStore = None
_config: Dict[str, Any] = None


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize Feast connection on Locust startup."""
    global _config
    
    environment.work_dir = ""
    LOCUST_WORK_DIR = os.environ.get("LOCUST_WORK_DIR", "/home/locust")
    
    if isinstance(environment.runner, MasterRunner):
        print("Running on master node, distributed mode")
        environment.work_dir = LOCUST_WORK_DIR
    else:
        print("Running on a worker or standalone mode")
    
    config_path = os.path.join(environment.work_dir, "feast_configuration.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            _config = json.load(f)
    else:
        # Default config for local testing
        _config = {
            "feast_repo_path": os.environ.get("FEAST_REPO_PATH", "/tmp/feast_benchmark"),
            "batch_size": int(os.environ.get("BATCH_SIZE", "100")),
            "number_of_rows": int(os.environ.get("NUM_ROWS", "500")),
            "num_features": int(os.environ.get("NUM_FEATURES", "50")),
        }
    
    environment.batch_size = _config.get("batch_size", 100)
    environment.number_of_rows = _config.get("number_of_rows", 500)
    environment.num_features = _config.get("num_features", 50)
    environment.feast_repo_path = _config.get("feast_repo_path", "/tmp/feast_benchmark")


class FeastOnlineRead(User):
    """Locust User class for Feast online feature retrieval benchmarks."""
    
    wait_time = constant(0.1)
    
    def on_start(self):
        """Initialize FeatureStore connection when user starts."""
        global _feature_store
        if _feature_store is None:
            repo_path = self.environment.feast_repo_path
            print(f"Initializing FeatureStore from {repo_path}")
            _feature_store = FeatureStore(repo_path=repo_path)
        
        self.fs = _feature_store
        self.num_features = self.environment.num_features
        self.feature_names = [
            f"bench_fv:feature_{i}" for i in range(self.num_features)
        ]
    
    @task(1)
    def test_single_vector(self):
        """Benchmark: Read single entity feature vector."""
        entity_id = str(np.random.randint(self.environment.number_of_rows))
        self.single_read(entity_rows=[{"user_id": f"user_{entity_id}"}])
    
    @task(3)
    def test_batch_vector(self):
        """Benchmark: Read batch of entity feature vectors."""
        entity_ids = [
            str(random.randint(0, self.environment.number_of_rows - 1))
            for _ in range(self.environment.batch_size)
        ]
        entity_rows = [{"user_id": f"user_{eid}"} for eid in entity_ids]
        self.batch_read(entity_rows=entity_rows)
    
    @stopwatch
    def single_read(self, entity_rows: List[Dict]):
        """Read features for a single entity."""
        return self.fs.get_online_features(
            features=self.feature_names,
            entity_rows=entity_rows
        ).to_dict()
    
    @stopwatch
    def batch_read(self, entity_rows: List[Dict]):
        """Read features for a batch of entities."""
        return self.fs.get_online_features(
            features=self.feature_names,
            entity_rows=entity_rows
        ).to_dict()


class FeastHTTPOnlineRead(User):
    """Locust User class for Feast HTTP Feature Server benchmarks."""
    
    wait_time = constant(0.1)
    
    def on_start(self):
        """Setup for HTTP-based feature retrieval."""
        self.num_features = self.environment.num_features
        self.feature_service = _config.get("feature_service", "bench_service")
        self.server_url = os.environ.get(
            "FEAST_SERVER_URL", 
            "http://localhost:6566"
        )
    
    @task(1)
    def test_single_vector_http(self):
        """Benchmark: HTTP API single entity read."""
        entity_id = str(np.random.randint(self.environment.number_of_rows))
        self.http_single_read(entity_id=entity_id)
    
    @task(3)
    def test_batch_vector_http(self):
        """Benchmark: HTTP API batch entity read."""
        entity_ids = [
            str(random.randint(0, self.environment.number_of_rows - 1))
            for _ in range(self.environment.batch_size)
        ]
        self.http_batch_read(entity_ids=entity_ids)
    
    @stopwatch
    def http_single_read(self, entity_id: str):
        """HTTP request for single entity features."""
        import requests
        payload = {
            "feature_service": self.feature_service,
            "entities": {"user_id": [f"user_{entity_id}"]}
        }
        response = requests.post(
            f"{self.server_url}/get-online-features",
            json=payload
        )
        return response.json()
    
    @stopwatch
    def http_batch_read(self, entity_ids: List[str]):
        """HTTP request for batch entity features."""
        import requests
        payload = {
            "feature_service": self.feature_service,
            "entities": {"user_id": [f"user_{eid}" for eid in entity_ids]}
        }
        response = requests.post(
            f"{self.server_url}/get-online-features",
            json=payload
        )
        return response.json()


if __name__ == "__main__":
    # Run single user for local testing
    run_single_user(FeastOnlineRead)
