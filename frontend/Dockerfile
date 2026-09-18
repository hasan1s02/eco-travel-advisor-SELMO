# ---------------------------------------------------------------------------
# React client: built with Vite, served as static files by nginx.
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
# Baked in at build time: Vite inlines import.meta.env into the bundle.
ARG VITE_RASA_URL=/rasa
ENV VITE_RASA_URL=$VITE_RASA_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
