FROM public.ecr.aws/amazoncorretto/amazoncorretto:8 AS pdffigures2-builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN yum install -y curl gzip tar unzip \
    && yum clean all

RUN curl -fsSL https://github.com/sbt/sbt/releases/download/v1.11.6/sbt-1.11.6.tgz \
        -o /tmp/sbt.tgz \
    && tar -xzf /tmp/sbt.tgz -C /opt \
    && ln -s /opt/sbt/bin/sbt /usr/local/bin/sbt

RUN mkdir -p /src \
    && curl -fsSL https://codeload.github.com/allenai/pdffigures2/zip/refs/heads/master \
        -o /tmp/pdffigures2.zip \
    && unzip -q /tmp/pdffigures2.zip -d /src \
    && mv /src/pdffigures2-master /src/pdffigures2 \
    && cd /src/pdffigures2 \
    && sbt compile \
    && mkdir -p /tmp/pdffigures2-dist/lib \
    && jar cf /tmp/pdffigures2-dist/pdffigures2.jar -C target/scala-2.12/classes . \
    && for cache_dir in /root/.ivy2 /root/.sbt /root/.cache/coursier; do \
        if [ -d "$cache_dir" ]; then \
            find "$cache_dir" -type f -name '*.jar' -exec cp -n {} /tmp/pdffigures2-dist/lib/ \; ; \
        fi; \
    done \
    && find /src/pdffigures2 -path '*/target/*' -type f -name '*.jar' \
        -exec cp -n {} /tmp/pdffigures2-dist/lib/ \;


FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TORCH_DEVICE=cpu \
    OCR_ENGINE=None \
    HF_HOME=/app/var/hf-cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        libgl1 \
        libglib2.0-0 \
        openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --python /usr/local/bin/python \
    && uv pip install --python .venv/bin/python marker-pdf

RUN mkdir -p /opt/pdffigures2
COPY --from=pdffigures2-builder /tmp/pdffigures2-dist /opt/pdffigures2
COPY docker/pdffigures2-wrapper.py /usr/local/bin/pdffigures2
RUN chmod +x /usr/local/bin/pdffigures2

COPY app ./app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
