FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r server/requirements.txt

COPY server/ ./server/

RUN mkdir -p /app/server/static/uploads

EXPOSE 5000

ENV GUNICORN_WORKERS=2

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:5000 \
     --worker-class gevent \
     --workers ${GUNICORN_WORKERS} \
     --worker-connections 1000 \
     --timeout 120 \
     'server.app:create_app()'"]
