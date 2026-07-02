# Multi-stage build для уменьшения размера образа
# Stage 1: builder — собираем зависимости + BSL LS
# Stage 2: runtime — только то что нужно для запуска

# ─── Stage 1: builder ───
FROM python:3.12-slim AS builder

LABEL maintainer="Pradushkoai"
LABEL description="1C AI Development Environment"

# Системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    git \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Копируем только pyproject.toml для pip install (кэширование слоёв)
# P1.3: requirements*.txt удалены, используем pyproject-only модель
COPY pyproject.toml ./
# README нужен для setuptools (readme = "README.md" в pyproject.toml)
COPY README.md ./

# Устанавливаем зависимости в отдельную директорию
RUN pip install --no-cache-dir --target=/build/deps \
    -e ".[dev]" 2>/dev/null || \
    pip install --no-cache-dir --target=/build/deps \
    pytest pytest-cov pytest-benchmark pytest-asyncio hypothesis lxml Pillow \
    ruff mypy structlog mcp python-dotenv networkx v8unpack

# Скачиваем BSL Language Server
RUN curl -sL "https://github.com/1c-syntax/bsl-language-server/releases/download/v1.0.1/bsl-language-server_nix.zip" -o /tmp/bsl-ls.zip && \
    mkdir -p /opt/bsl-language-server && \
    unzip -q /tmp/bsl-ls.zip -d /opt/bsl-language-server/ && \
    chmod +x /opt/bsl-language-server/bsl-language-server/bin/bsl-language-server && \
    rm /tmp/bsl-ls.zip

# ─── Stage 2: runtime ───
FROM python:3.12-slim AS runtime

LABEL maintainer="Pradushkoai"
LABEL description="1C AI Development Environment"

# Только JRE (не JDK) для запуска BSL LS
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости из builder
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages/
COPY --from=builder /opt/bsl-language-server /opt/bsl-language-server

# Symlink для bsl-language-server
RUN ln -sf /opt/bsl-language-server/bsl-language-server/bin/bsl-language-server /usr/local/bin/bsl-language-server && \
    chmod +x /usr/local/bin/bsl-language-server

# Копируем исходники проекта (только нужное)
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY templates/ /app/templates/
COPY knowledge_base/ /app/knowledge_base/
COPY pyproject.toml README.md manifest.json paths.env paths.py /app/

# Устанавливаем пакет (без зависимостей — они уже скопированы)
RUN pip install --no-cache-dir --no-deps -e .

# Создаём 4-слойную структуру
RUN mkdir -p /app/data/configs /app/data/archives /app/data/hbk \
    /app/derived/configs /app/derived/platform \
    /app/tools/repos \
    /app/runtime /app/learned-skills

# Environment
ENV PROJECT_DIR=/app \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    PATH="${PATH}:/usr/local/bin" \
    LOG_FORMAT=console \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# Healthcheck — проверяем что CLI работает
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD 1c-ai validate || exit 1

# Проверка при сборке
RUN python3 -c "from src.project import Project; print('✅ Package OK')" && \
    bsl-language-server --version 2>&1 | grep -i version && \
    echo "✅ BSL LS OK"

# Точка входа — CLI
ENTRYPOINT ["1c-ai"]
CMD ["--help"]
