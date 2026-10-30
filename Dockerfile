FROM python:3.10-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Step 1: Pre-install python dependencies for optimal layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Step 2: Copy repository source files
COPY . .

# Step 3: Install the phalanx package
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

CMD ["python3", "-m", "phalanx.cli", "serve"]
