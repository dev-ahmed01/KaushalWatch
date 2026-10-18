FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /workstation
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    useradd --uid 10001 --create-home --shell /usr/sbin/nologin worker
COPY kwtrust ./kwtrust
COPY scripts/start.sh ./scripts/start.sh
RUN chmod +x ./scripts/start.sh && mkdir -p /output && \
    chown -R worker:worker /workstation /output
USER worker
EXPOSE 8765
ENTRYPOINT ["./scripts/start.sh"]
