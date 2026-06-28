FROM python:3.12-slim

LABEL maintainer="Pradushkoai"
LABEL description="1C AI Development Environment"

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    git \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем проект
COPY . /app/

# Устанавливаем Python-пакет
RUN pip install --no-cache-dir -e ".[dev]"

# Устанавливаем BSL Language Server
RUN curl -sL "https://github.com/1c-syntax/bsl-language-server/releases/download/v1.0.1/bsl-language-server_nix.zip" -o /tmp/bsl-ls.zip && \
    mkdir -p /opt/bsl-language-server && \
    unzip -q /tmp/bsl-ls.zip -d /opt/bsl-language-server/ && \
    ln -sf /opt/bsl-language-server/bsl-language-server/bin/bsl-language-server /usr/local/bin/bsl-language-server && \
    chmod +x /opt/bsl-language-server/bsl-language-server/bin/bsl-language-server && \
    rm /tmp/bsl-ls.zip

# Создаём 4-слойную структуру
RUN mkdir -p /app/data/configs /app/data/archives /app/data/hbk \
    /app/derived/configs /app/derived/platform \
    /app/tools/repos \
    /app/runtime /app/scripts /app/learned-skills

# Environment
ENV PROJECT_DIR=/app
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${PATH}:/usr/local/bin"

# Проверка
RUN python3 -c "from src.project import Project; print('✅ Package OK')" && \
    bsl-language-server --version 2>&1 | grep version && \
    echo "✅ BSL LS OK"

# Точка входа
ENTRYPOINT ["1c-ai"]
CMD ["--help"]
