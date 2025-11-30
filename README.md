# USGS Water Data Metrics

Python flask app that exposes Prometheus-style time-series metrics for streamflow gauges provided by the [USGS Water Data OGC APIs](https://api.waterdata.usgs.gov/ogcapi/v0/), under the latest continuous data collection.

## Installation

This Prometheus exporter is intended to run in Docker, however technically they can run under any Python 3 distribution.

### Dependencies

If installing using the Docker image build, the requirements.txt contains the needed dependencies that must be installed for the exporter to compile and run.

Dependencies are:

Flask
prometheus_client
PyYAML
requests
urllib3

If you're installing the exporter in another Python environment, ensure your host has these dependencies installed i.e. ```pip install prometheus_client```. If you're running in a Python virtual environment ensure the dependencies are installed there.

At that point you may run the exporter and connect to the metrics page at http://127.0.0.1:8000/metrics.

### Docker

#### Building the Image

Building the docker image is straight-forward and standard. Place all files in the same folder, and use compose to build the image using ```docker compose build```.

#### Docker File

You can run the image from the Docker file:

```bash
    docker run -d -p 8001:8001 -v ./usgs_gauges.yaml:/config/usgs_gauges.yaml ikluhsman/usgs_exporter:latest
```

#### Docker Compose

After building the image you can run it with docker compose:

```
usgs_exporter:
    build: ./
    image: ikluhsman/usgs_exporter:latest
    container_name: usgs_exporter
    ports:
      - "${HOST_IP}:8001:8001" # HOST_IP in env_file
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./usgs_gauges.yaml:/config/usgs_gauges.yaml
```
Adapt to portainer if you wish or whatever other containerization platform you use.

## Configuration

Configuration can be done using environment variables in a .env file, ensure you use environment variables in your docker image or compose file.

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| USGS_API_KEY | xxx | Request an API key from the [USGS Water Data OGC APIs](https://api.waterdata.usgs.gov/ogcapi/v0/) page. |
| USGS_API_KEY2 | xxx | A backup API key to use in case of lockout while tuning workers. |
| USGS_MAX_WORKERS | 10 | How many gauges/threads to query at a time. |

### Gauges File usgs_gauges.yaml

The gauges file contains the data needed to query the API for each gauge that you want to pull metrics for. Gauges are designed to gather latest continuous data from each gauge in Cubic Feet Per second. API parameters are documented at the [USGS Water Data OGC APIs Latest Continuous Reference Page](https://api.waterdata.usgs.gov/ogcapi/v0/openapi?f=html#/latest-continuous) You may request your own API there and include it in the .env file.

## Usage

After the exporter is running access it using: http://127.0.0.1:8000/metrics, lining up your host address and port with the host and port selected as you ran the flask app.

You will get an html page displaying the exposed metrics for the exporter as defined in the gauges.yaml configuration file.

Metrics are Time-Series telemetry metrics that may be scraped using a tool such as Prometheus.

## Metrics
| Name | Description | Category | Type |
| :--- | :--- | :--- | :--- |
| python_gc_objects_collected_total | Objects collected during gc | Python | counter |
| python_gc_objects_uncollectable_total | Uncollectable objects found during GC | Python | counter |
| python_gc_collections_total | Number of times this generation was collected | Python | counter |
| python_info | Python platform information | Python | gauge |
| process_virtual_memory_bytes | Virtual memory size in bytes. | System | gauge |
| process_resident_memory_bytes | Resident memory size in bytes. | System | gauge |
| process_start_time_seconds | Start time of the process since unix epoch in seconds. | System | gauge |
| process_cpu_seconds_total | Total user and system CPU time spent in seconds. | System | counter |
| process_open_fds | Number of open file descriptors. | System | gauge |
| process_max_fds | Maximum number of open file descriptors. | System | gauge |
| usgs_streamflow_cfs | Gauge streamflow data in cubic feet per second. | USGS | gauge |
| usgs_exporter_scrape_success_total | Number of successful gauge fetches. | USGS | gauge |
| usgs_exporter_scrape_failure_total | Total number of failed gauge fetches | USGS | gauge |
| usgs_exporter_gauges_total | Total number of gauges configured for polling | USGS | gauge |
| usgs_exporter_scrape_duration_seconds | Time spent scraping all gauges | USGS | gauge |

