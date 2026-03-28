FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl bubblewrap && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/repoaudit_clones && \
    chmod +x start.sh

EXPOSE 7860

CMD ["./start.sh"]