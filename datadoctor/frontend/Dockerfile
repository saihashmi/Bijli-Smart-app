# syntax=docker/dockerfile:1
# DataDoctor AI web app. Build from the datadoctor/ folder:  docker build -f frontend/Dockerfile .
FROM node:22-slim AS build
WORKDIR /srv/frontend
COPY frontend/package.json frontend/package-lock.json ./
# Behind a TLS-inspecting proxy, pass its CA as a build secret:  --secret id=ca,src=/path/to/ca.crt
RUN --mount=type=secret,id=ca,required=false \
    if [ -s /run/secrets/ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca; fi; \
    npm ci
COPY frontend/ .
# Baked in at build time: where /api is forwarded, and the proxy body limit (keep equal to the API's limit).
ARG BACKEND_URL=http://backend:8000
ARG MAX_UPLOAD_MB=20
ENV BACKEND_URL=$BACKEND_URL MAX_UPLOAD_MB=$MAX_UPLOAD_MB NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-slim AS run
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /srv/frontend
COPY --from=build /srv/frontend/.next/standalone ./
COPY --from=build /srv/frontend/.next/static ./.next/static
COPY --from=build /srv/frontend/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
