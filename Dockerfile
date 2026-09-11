FROM python:3.13-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production DATA_DIR=/data HF_HOME=/data/models
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-liberation && rm -rf /var/lib/apt/lists/* \
    && useradd -u 10001 -m studio && mkdir /data && chown studio:studio /data
WORKDIR /app
COPY requirements.txt requirements-ai.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ARG ENABLE_TRANSCRIPTION=0
RUN if [ "$ENABLE_TRANSCRIPTION" = "1" ]; then pip install --no-cache-dir -r requirements-ai.txt; fi
COPY server ./server
COPY studio ./studio
USER studio
EXPOSE 8000
CMD ["python", "-m", "server"]
