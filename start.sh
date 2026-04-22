#!/bin/bash
exec gunicorn main:app \
  --bind 0.0.0.0:${PORT:-8080} \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --preload \
  --max-requests 500 \
  --max-requests-jitter 50 \
  --worker-tmp-dir /dev/shm
