FROM python:3.13-slim

WORKDIR /app

COPY relay_webhook.py /app/relay_webhook.py
COPY run_webhook.sh /app/run_webhook.sh
COPY config.example.json /app/config.example.json

RUN chmod +x /app/run_webhook.sh

EXPOSE 8780

CMD ["/app/run_webhook.sh"]
