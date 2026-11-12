"""gunicorn settings for Railway. Railway sets $PORT."""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
# One process keeps memory low and the per-IP rate limits accurate;
# threads handle concurrent requests while Gemini calls are waiting.
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "8"))
# Gemini with several tool calls can take a while.
timeout = 120
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "*"
