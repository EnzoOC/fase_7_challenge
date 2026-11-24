# Dashboard React (Vite) — build em Node e serviço estático em nginx SEM root.
FROM docker.io/library/node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# nginx do repositório do Alpine (recebe correções de segurança mais rápido
# que a imagem oficial) + todos os pacotes atualizados no build.
FROM docker.io/library/alpine:3.24
RUN apk upgrade --no-cache \
    && apk add --no-cache nginx \
    && rm -f /etc/nginx/http.d/default.conf
COPY nginx-main.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/http.d/agrosmart.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
