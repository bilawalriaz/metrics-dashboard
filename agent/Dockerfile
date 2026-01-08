FROM python:3.12-slim

LABEL maintainer="bilawal@hyperflash.uk"
LABEL description="System Metrics Agent for VPS monitoring"

WORKDIR /app

# Add group for Docker socket access
RUN groupadd -r docker && useradd -r -g docker metrics-user

COPY agent.py /app/agent.py

EXPOSE 8000

USER metrics-user

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/metrics')" || exit 1

CMD ["python3", "-u", "agent.py"]
