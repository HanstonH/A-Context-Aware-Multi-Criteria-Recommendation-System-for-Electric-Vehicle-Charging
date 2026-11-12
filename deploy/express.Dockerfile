# Express API. Build context: repo root (it needs database/schema.sql).
# Railway: Root Directory = "/" and variable RAILWAY_DOCKERFILE_PATH=deploy/express.Dockerfile

# better-sqlite3 is a native module; build tools are only needed if no prebuilt
# binary matches, and they stay in this stage.
FROM node:24-slim AS deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 make g++ \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app/ev-charging-backend
COPY ev-charging-backend/package.json ev-charging-backend/package-lock.json ./
RUN npm ci --omit=dev

FROM node:24-slim
ENV NODE_ENV=production \
    DB_PATH=/data/ev_charging.db \
    DB_SCHEMA_PATH=/app/database/schema.sql
WORKDIR /app/ev-charging-backend
COPY --from=deps /app/ev-charging-backend/node_modules ./node_modules
COPY ev-charging-backend/ ./
COPY database/schema.sql /app/database/schema.sql
# Railway sets PORT; index.js falls back to 5000.
CMD ["node", "index.js"]
