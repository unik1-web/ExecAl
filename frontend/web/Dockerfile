FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache ca-certificates

ARG NPM_REGISTRY=https://registry.npmjs.org/
ENV npm_config_registry=${NPM_REGISTRY} \
    npm_config_loglevel=info \
    npm_config_fund=false \
    npm_config_audit=false \
    npm_config_fetch_retries=5 \
    npm_config_fetch_retry_maxtimeout=600000 \
    npm_config_fetch_retry_mintimeout=10000

COPY package.json package-lock.json* /app/
RUN npm install --no-audit --no-fund

COPY . /app

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

