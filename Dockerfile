# Build the React site without baking any server-side secrets into public assets.
FROM node:22-alpine AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Serve the compiled React site and the Python API from the same origin.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-build /workspace/frontend/dist ./frontend/dist
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.serve:app --host 0.0.0.0 --port ${PORT:-10000}"]
