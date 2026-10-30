FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SUPPORTRECALL_DATA_DIR=/app/data \
    HF_HOME=/home/supportrecall/.cache/huggingface

WORKDIR /app

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
    && groupadd --system --gid 10001 supportrecall \
    && useradd --system --uid 10001 --gid supportrecall --home-dir /home/supportrecall supportrecall \
    && mkdir -p /app/data /app/uploads /app/vectors /home/supportrecall/.cache/huggingface \
    && chown -R supportrecall:supportrecall /app /home/supportrecall

COPY --chown=10001:10001 app/ ./app/

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
