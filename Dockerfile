# Stage 1: build the website (static files)
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npx next build

# Stage 2: Python API that also serves the website
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=web /web/out ./frontend/out
RUN mkdir -p /app/data && chmod 777 /app/data
ENV STATIC_DIR=/app/frontend/out DB_PATH=/app/data/validate.db PORT=8000
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
