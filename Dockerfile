# SupportFlow Agent · 阶段 2 运行镜像
#
# 单阶段构建即可满足当前目标：依赖由 uv 解析并锁定（uv.lock），源码从 src/ 拷入。
# 容器内不执行迁移 —— 由 compose 的 migrate 一次性服务负责，保持「建表」与
# 「起服务」两个关注点分离。

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# uv 官方推荐安装方式（固定版本，避免构建漂移）。
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

WORKDIR /app

# 先只拷贝依赖清单：只要它们不变，这一层就能命中缓存。
# README.md 必须一起拷：pyproject 声明了 readme，hatchling 读取元数据时需要它。
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY alembic.ini pyproject.toml uv.lock ./
COPY migrations ./migrations
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# 默认命令交给 compose 指定（migrate / api / worker / seed 共用一个镜像）。
CMD ["uvicorn", "supportflow.bootstrap.api:app", "--host", "0.0.0.0", "--port", "8000"]
