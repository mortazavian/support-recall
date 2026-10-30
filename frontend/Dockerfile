FROM node:24-alpine AS build

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig*.json ./
COPY src ./src
RUN npm run build

FROM nginx:1.29-alpine

COPY --from=build --chown=101:101 /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

USER 101:101
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
