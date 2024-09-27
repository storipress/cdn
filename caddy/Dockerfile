FROM ghcr.io/storipress/caddy:latest

ARG redis_db
ENV REDIS_DB=$redis_db
ARG api_endpoint
ENV API_ENDPOINT=$api_endpoint
ARG environment
ENV ENVIRONMENT=$environment

WORKDIR /usr/local/caddy

COPY src /usr/local/caddy
COPY listener /usr/local/listener
COPY supervisord.conf /etc/supervisord.conf

RUN mkdir -p /usr/local/caddy/files && mkdir -p /usr/local/caddy/locks

EXPOSE 80
EXPOSE 443
EXPOSE 2019

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
