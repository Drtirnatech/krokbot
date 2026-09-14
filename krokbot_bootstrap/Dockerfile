FROM alpine:3.20

RUN apk add --no-cache python3 py3-pip curl jq docker-cli ca-certificates

WORKDIR /app
COPY bootstrap.py /app/bootstrap.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
