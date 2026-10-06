FROM node:22-alpine@sha256:968df39aedcea65eeb078fb336ed7191baf48f972b4479711397108be0966920 AS build
WORKDIR /app
COPY display/package*.json ./
RUN npm ci
COPY display/ ./
ARG GIT_HASH=unknown
RUN VITE_APP_BUILD=${GIT_HASH} npm run build

FROM nginx:1.30-alpine@sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94 AS runtime
RUN apk upgrade --no-cache
COPY --from=build /app/dist /usr/share/nginx/html
COPY display/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1
