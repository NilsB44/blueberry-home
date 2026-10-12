# Builds the web app and bakes it into a Caddy image that also proxies /api.
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /src/build /srv/web
COPY Caddyfile /etc/caddy/Caddyfile
