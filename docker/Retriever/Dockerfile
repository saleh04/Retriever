FROM ghcr.io/astral-sh/uv:0.12.15-python3.12-trixie

WORKDIR /app

# Install additional systemdependencies
RUN apt-get update && apt-get install -y  \
    build-essential \
    libavif-dev pkg-config \
    libjpeg-dev \
    gcc unzip zip \
    python3-dev \
    libxml2-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY src/requirements.txt .

RUN uv pip install --no-cache-dir -r requirements.txt --system

COPY src/ .

# Create directory structure for Alembic
RUN mkdir -p /app/models/db_schemes/Retriever/

# Copy Alembic configuration file
COPY docker/Retriever/alembic.ini /app/models/db_schemes/Retriever/alembic.ini

COPY docker/Retriever/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]