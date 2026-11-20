# Next.js frontend. Build context: frontend/ (Railway: Root Directory = "/frontend").
# A Dockerfile pins the package manager: this folder has both pnpm and npm lockfiles.
FROM node:24-slim AS build
RUN corepack enable && corepack prepare pnpm@11.4.0 --activate
WORKDIR /app
# pnpm-workspace.yaml holds allowBuilds; pnpm 11 refuses to install without it.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# NEXT_PUBLIC_* values are baked into the browser bundle at build time.
# Railway passes service variables to the build for each ARG declared here.
ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
ARG NEXT_PUBLIC_GOOGLE_MAP_ID
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:24-slim
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=build /app ./
# next start reads PORT (set by Railway).
CMD ["node_modules/.bin/next", "start"]
