# Feast Benchmark Image
# Build: docker build -t feast-benchmark:latest .
# Push:  docker push quay.io/your-org/feast-benchmark:latest

FROM python:3.11-slim

LABEL maintainer="feast-benchmark"
LABEL description="Feast online store benchmark suite"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    'feast[redis,aws,postgres]' \
    'psycopg[binary,pool]>=3.0.0' \
    'redis>=4.0.0' \
    'aiobotocore' \
    'matplotlib>=3.5.0'

# Copy benchmark code
COPY unified_benchmark.py .
COPY generate_charts.py .
COPY benchmark_config.py .
COPY common/ ./common/

# Create results directory
RUN mkdir -p /results

# Default command
ENTRYPOINT ["python", "unified_benchmark.py"]
CMD ["--help"]
