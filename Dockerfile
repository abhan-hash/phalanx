FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging and dependencies
COPY pyproject.toml setup.py requirements.txt README.md ./
RUN pip install --no-cache-dir -e .

# Copy application source, data, scenarios, personas, and pre-computed runs
COPY src/ ./src/
COPY personas/ ./personas/
COPY scenarios/ ./scenarios/
COPY runs/ ./runs/
COPY phalanx_report.sarif regression_vault.json ./

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000

CMD ["python3", "-m", "phalanx.cli", "serve"]
