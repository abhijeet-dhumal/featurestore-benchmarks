# Feast Benchmark Image
#===============================================================================
# Build with custom feast git reference:
#   docker build --build-arg FEAST_GIT_REF=my-branch -t feast-benchmark:latest .
#
# Build with PyPI feast:
#   docker build --build-arg FEAST_SOURCE=pypi -t feast-benchmark:latest .
#===============================================================================

FROM python:3.11-slim

LABEL maintainer="feast-benchmark"
LABEL description="Feast online store benchmark suite"

# Build arguments for feast installation
ARG FEAST_SOURCE="git"
ARG FEAST_GIT_URL="https://github.com/feast-dev/feast.git"
ARG FEAST_GIT_REF="master"
ARG FEAST_EXTRAS="redis,aws,postgres"
ARG FEAST_VERSION=">=0.40.0"

# Store as env vars for runtime reference
ENV FEAST_SOURCE=${FEAST_SOURCE}
ENV FEAST_GIT_URL=${FEAST_GIT_URL}
ENV FEAST_GIT_REF=${FEAST_GIT_REF}

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install all feast core dependencies first (from official pyproject.toml)
RUN pip install --no-cache-dir \
    'click>=7.0.0,<9.0.0' \
    'colorama>=0.3.9,<1' \
    'dill~=0.3.0' \
    'protobuf>=4.24.0' \
    'Jinja2>=2,<4' \
    'jsonschema' \
    'mmh3' \
    'numpy>=1.24,<3' \
    'pandas>=1.4.3,<3' \
    'pyarrow>=12.0.0' \
    'pydantic>=2.0' \
    'pygments>=2.12.0,<3' \
    'PyYAML>=5.4.0,<7' \
    'requests' \
    'SQLAlchemy>1' \
    'tabulate>=0.8.0,<1' \
    'tenacity>=7,<9' \
    'toml>=0.10.0,<1' \
    'tqdm>=4,<5' \
    'typeguard>=4.0.0' \
    'fastapi>=0.68.0' \
    'uvicorn>=0.22.0' \
    'gunicorn' \
    'dask[dataframe]>=2023.0' \
    'prometheus_client' \
    'psutil' \
    'bigtree>=0.19.2' \
    'pyjwt' \
    'orjson>=3.9.0' \
    'boto3>=1.28.0' \
    'fsspec' \
    'aiobotocore>2,<3' \
    'psycopg[binary,pool]>=3.0.0' \
    'redis>=4.2.2,<5' \
    'hiredis>=2.0.0,<3' \
    'matplotlib>=3.5.0'

# Install feast based on source type
RUN if [ "$FEAST_SOURCE" = "git" ]; then \
        echo "Installing feast from git: ${FEAST_GIT_URL}@${FEAST_GIT_REF}"; \
        pip install --no-cache-dir --no-deps \
            "feast[${FEAST_EXTRAS}] @ git+${FEAST_GIT_URL}@${FEAST_GIT_REF}#subdirectory=sdk/python"; \
    else \
        echo "Installing feast from PyPI: ${FEAST_VERSION}"; \
        pip install --no-cache-dir --no-deps \
            "feast[${FEAST_EXTRAS}]${FEAST_VERSION}"; \
    fi

# Copy benchmark code (only files used by K8s jobs)
COPY unified_benchmark.py .
COPY generate_charts.py .

# Create results directory
RUN mkdir -p /results

# Default command
ENTRYPOINT ["python", "unified_benchmark.py"]
CMD ["--help"]
