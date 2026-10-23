# ---------- AI Music Marketer API ----------
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

ENV APP_DATABASE_URL=sqlite:////data/music_marketer.db
ENV APP_MEDIA_STORAGE_PATH=/data/private-media
RUN mkdir -p /data && useradd --create-home appuser && chown -R appuser /data /app
USER appuser
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
