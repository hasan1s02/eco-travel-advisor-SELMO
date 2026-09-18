# ---------------------------------------------------------------------------
# Hugging Face Spaces (Docker SDK) — single-container deployment.
#
# Spaces exposes exactly one port (7860), so nginx sits in front: it serves the
# built React client and proxies /rasa to the Rasa server running inside the
# same container. The action server runs alongside on 5055, never exposed.
#
# Build context is the REPOSITORY ROOT:
#     docker build -f deploy/huggingface/Dockerfile -t eco-travel-advisor .
#
# To publish:
#   1. Train the model first:  rasa train --fixed-model-name eco_travel_advisor
#   2. Create a Space, SDK = Docker, hardware = CPU basic (free)
#   3. Push this repo, with this file copied to the Space root as ./Dockerfile
#   4. Add API keys as Space *secrets* (never as plain variables)
# ---------------------------------------------------------------------------

FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_RASA_URL=/rasa
RUN npm run build


FROM rasa/rasa:3.6.21-full

USER root
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx supervisor curl \
 && rm -rf /var/lib/apt/lists/*

# Action-server dependencies. rasa-sdk is already in the base image.
COPY requirements-actions.txt /tmp/requirements-actions.txt
RUN pip install --no-cache-dir -r /tmp/requirements-actions.txt

COPY models/ /app/models/
COPY actions/ /app/actions/
COPY domain.yml config.yml credentials.yml /app/
COPY data/ /app/data/

# In one container the action server is simply on localhost.
RUN printf 'action_endpoint:\n  url: "http://localhost:5055/webhook"\n' > /app/endpoints.yml

COPY --from=frontend /build/dist /var/www/html
COPY deploy/huggingface/nginx.conf /etc/nginx/sites-available/default
COPY deploy/huggingface/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Spaces runs the container as a non-root user with UID 1000.
RUN useradd -m -u 1000 spaceuser 2>/dev/null || true \
 && mkdir -p /var/log/supervisor /var/lib/nginx /var/log/nginx /run \
 && chown -R 1000:1000 /app /var/www/html /var/log/supervisor /var/lib/nginx /var/log/nginx /run

USER 1000
ENV HOME=/home/spaceuser
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS http://localhost:7860/ || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
