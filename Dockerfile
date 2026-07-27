# 智慧生活管家 API — 容器化以便部署到 ECS Fargate／App Runner（[ADR-0018]）
#
# 為什麼是常駐容器而不是 Lambda：主辦提供 AWS 額度，選型的目標函數是**體感速度**，
# 而 Lambda 冷啟動直接打在評審的第一印象上。同一個映像也能跑 Lambda 容器映像，
# 所以這個決定是可逆的（ADR-0004 的介面隔離就是為了保住這種可逆性）。

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 先只複製相依定義，讓 layer 快取在原始碼變動時仍然有效
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY agent/ ./agent/
COPY api/ ./api/
COPY core/ ./core/
COPY mcp_server/ ./mcp_server/
COPY raw_data/ ./raw_data/
COPY main.py ./

# 設定一律走環境變數：容器裡沒有 .env（見 core/config.py）
ENV DATA_DIR=/data \
    PORT=8000
RUN mkdir -p /data

EXPOSE 8000

# ALB／App Runner 的健康檢查目標
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/healthz', timeout=2).status == 200 else 1)"

CMD ["sh", "-c", "uv run --no-dev uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
