FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3030

CMD ["npx", "vite", "--port", "3030", "--host"]
