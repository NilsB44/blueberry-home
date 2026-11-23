# Builds the web app and bakes it into a Caddy image that also proxies /api.
# Built from the repository root (see compose.yml) so the home page can include MILESTONES.md.
FROM node:26-alpine AS build
WORKDIR /src
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
COPY MILESTONES.md /MILESTONES.md
ARG HUB_VERSION=""
RUN VITE_HUB_VERSION="$HUB_VERSION" npm run build

FROM caddy:2-alpine
COPY --from=build /src/build /srv/web
COPY web/Caddyfile /etc/caddy/Caddyfile
