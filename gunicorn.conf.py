"""Gunicorn production settings for the PaperVault web service."""

from __future__ import annotations

import os


bind = os.getenv("GUNICORN_BIND", f"0.0.0.0:{os.getenv('PORT', '5001')}")
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = "gthread"

# AI provider calls may legitimately take longer than an ordinary search.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# The paper corpus is read-mostly. Loading it before workers are forked lets
# Linux share its memory pages between workers through copy-on-write.
preload_app = True

accesslog = "-"
errorlog = "-"
capture_output = True
