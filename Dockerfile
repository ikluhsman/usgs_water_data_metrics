FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update -y && \
    apt-get install -y curl
COPY usgs_exporter.py .
COPY ./usgs_gauges.yaml /config/usgs_gauges.yaml
CMD ["python", "usgs_exporter.py"]

