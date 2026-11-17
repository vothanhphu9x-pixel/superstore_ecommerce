FROM node:22-alpine

ENV NODE_ENV=production
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

COPY collection.js run.js ./

USER 10001:10001
ENTRYPOINT ["node", "/app/run.js"]
