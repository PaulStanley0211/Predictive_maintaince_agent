#!/bin/bash
# Azure App Service startup command (Linux only — gunicorn requires fcntl)
gunicorn src.api.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
