"""Local development server: `python -m backend` from the repo root.

gunicorn doesn't run on Windows, so this uses Flask's own server (debug off).
Production on Railway uses gunicorn (see gunicorn.conf.py).
"""

import os

from .server import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"MapExplore backend on http://0.0.0.0:{port}  (Ctrl+C to stop)")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
