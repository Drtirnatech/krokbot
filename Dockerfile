FROM python:3.12-slim

WORKDIR /app

# Install system utilities and build tools for llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install llama-cpp-python server runtime
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "llama-cpp-python[server]"

# Install project requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose KrokBot Dashboard (5150), Host API Bridge (8990), and Llama.cpp (8081)
EXPOSE 5150 8990 8081

ENV MODEL_PATH=/app/models/Qwen3-4B-Q4_K_M.gguf
ENV LLAMACPP_HOST=http://127.0.0.1:8081
ENV LLM_MODEL=qwen3-4b
ENV PYTHONUNBUFFERED=1

CMD ["python", "run_krokbot.py"]
