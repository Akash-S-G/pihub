FROM python:3.11-slim@sha256:a5b427ace4900267d93db34138e512325c6fa6af84ad5e4ed5f3b36258cc4142 AS llama-builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ninja-build \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp.git
WORKDIR /opt/llama.cpp
RUN cmake -B build -DGGML_NATIVE=OFF -DLLAMA_BUILD_SERVER=ON -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --target llama-server -j2

FROM python:3.11-slim@sha256:a5b427ace4900267d93db34138e512325c6fa6af84ad5e4ed5f3b36258cc4142

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PYTHONPATH=/app \
    PATH=/opt/llama.cpp/build/bin:$PATH \
    LD_LIBRARY_PATH=/opt/llama.cpp/build/bin:/opt/llama.cpp/build/src:/opt/llama.cpp/build/common

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 && rm -rf /var/lib/apt/lists/*

COPY --from=llama-builder /opt/llama.cpp/build/bin/ /opt/llama.cpp/build/bin/
COPY --from=llama-builder /opt/llama.cpp/build/src/ /opt/llama.cpp/build/src/
COPY --from=llama-builder /opt/llama.cpp/build/common/ /opt/llama.cpp/build/common/
COPY inference-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r /tmp/requirements.txt

COPY shared /app/shared
COPY inference-service/app /app/app

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
