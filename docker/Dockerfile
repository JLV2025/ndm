# 多阶段构建
# 阶段 1: 构建前端
FROM node:20-alpine AS build-frontend
WORKDIR /app/frontend
COPY frontend/ .
RUN npm ci --only-fetch=1 && npm run build

# 阶段 2: 构建后端
FROM python:3.11-slim AS build-backend
WORKDIR /app/backend
COPY backend/ .
COPY --from=build-frontend /app/frontend/dist /app/backend/frontend
RUN pip install --no-cache-dir -r requirements.txt

# 阶段 3: 生产镜像
FROM python:3.11-slim AS production
WORKDIR /app
COPY --from=build-backend /app/backend/ .
COPY --from=build-backend /app/backend/frontend /app/backend/frontend

# 安装 nginx
RUN apt-get update && apt-get install -y \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 nginx 配置
COPY docker/nginx.conf /etc/nginx/nginx.conf

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 80 8000

ENV PYTHONUNBUFFERED=1
ENV DATA_ROOT=/app/data

CMD ["nginx", "-g", "daemon off;"]
