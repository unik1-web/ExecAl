FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* /app/
RUN npm install --no-audit --no-fund

COPY . /app

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

