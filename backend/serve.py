"""Production ASGI entrypoint: serve the built React SPA and FastAPI together.

Local development intentionally continues to use backend.main:app with Vite.
Docker/Render use backend.serve:app so the browser's same-origin /api calls work.
"""
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from .main import app

_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if not (_DIST / "index.html").is_file():
    raise RuntimeError("Frontend build not found. Run 'cd frontend && npm run build' before starting backend.serve:app.")

# Keep this as the LAST mount: previously registered /api/* routes take priority.
app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="casewise-frontend")
