#!/usr/bin/env python3
from flask import Flask, Response
import requests
import os
import yaml
import time
from prometheus_client import Gauge, Counter, Summary, generate_latest, CONTENT_TYPE_LATEST
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# Prometheus metrics
USGS_STREAMFLOW = Gauge(
    "usgs_streamflow_cfs",
    "USGS streamflow in cubic feet per second",
    ["gauge_id", "friendly_name", "location_name"]
)

SCRAPE_SUCCESS = Gauge(
    "usgs_exporter_scrape_success_total",
    "Number of successful gauge fetches"
)

SCRAPE_FAILURE = Gauge(
    "usgs_exporter_scrape_failure_total",
    "Total number of failed gauge fetches"
)

GAUGES_TOTAL = Gauge(
    "usgs_exporter_gauges_total",
    "Total number of gauges configured for polling"
)

SCRAPE_DURATION = Gauge(
    "usgs_exporter_scrape_duration_seconds",
    "Time spent scraping all gauges"
)

USGS_API_RATELIMIT_REMAINING = Gauge(
    "usgs_api_ratelimit_remaining",
    "Remaining allowed requests per hour for each USGS API key",
    ["api_key_label"]
)

USGS_API_RATELIMIT_LIMIT = Gauge(
    "usgs_api_ratelimit_limit",
    "Limit of allowed requests per hour.",
    ["api_key_label"]
)

USGS_API_REQUESTS_PER_HOUR = Gauge(
    "usgs_api_requests_per_hour",
    "Number of USGS API requests used in the current hour",
    ["api_key_label"]
)

# Configuration
GAUGES_FILE = "/config/usgs_gauges.yaml"
MAX_WORKERS = int(os.getenv("USGS_MAX_WORKERS", 10))
API_KEY_PRIMARY = os.getenv("USGS_API_KEY")
API_KEY_BACKUP = os.getenv("USGS_API_KEY2")
API_URL = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items"

# Requests session with retries
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("http://", adapter)
session.mount("https://", adapter)


def load_gauges():
    try:
        with open(GAUGES_FILE, "r") as f:
            gauges = yaml.safe_load(f)
        if not isinstance(gauges, list):
            raise ValueError("gauges.yaml must be a list")
        for g in gauges:
            if not isinstance(g, dict) or "id" not in g:
                raise ValueError(f"Malformed gauge entry: {g}")
        return gauges
    except Exception as e:
        print(f"[ERROR] Loading gauges.yaml: {e}")
        return []


def fetch_usgs_gauge(gauge_id: str):
    """Fetch latest discharge value from USGS API, using primary then backup key"""
    params = {
        "monitoring_location_id": f"USGS-{gauge_id}",
        "parameter_code": "00060",   # discharge (cfs)
        "statistic_id": "00011",     # instantaneous
        "properties": "value,time"
    }

    # Try primary key first
    for key_label, api_key in [("primary", API_KEY_PRIMARY), ("backup", API_KEY_BACKUP)]:
        headers = {"X-Api-Key": api_key} if api_key else {}
        try:
            r = session.get(API_URL, headers=headers, params=params, timeout=10)
            r.raise_for_status()

            # Update rate limit metric
            remaining = r.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                try:
                    USGS_API_RATELIMIT_REMAINING.labels(api_key_label=key_label).set(int(remaining))
                except ValueError:
                    pass
            # Update limit metric
            limit = r.headers.get("X-RateLimit-Limit")
            if limit is not None:
                try:
                    USGS_API_RATELIMIT_LIMIT.labels(api_key_label=key_label).set(int(limit))
                except ValueError:
                    pass

            # Track API requests
            used = int(limit) - int(remaining)
            USGS_API_REQUESTS_PER_HOUR.labels(key_label).set(used)

            data = r.json()
            features = data.get("features", [])
            if features:
                raw_val = features[0]["properties"].get("value")
                if isinstance(raw_val, dict):
                    return float(raw_val.get("value", float("nan")))
                return float(raw_val)
            return float("nan")
        except requests.HTTPError as he:
            if r.status_code == 429:
                # Rate limit exceeded, try next key
                continue
            print(f"[WARN] HTTP error for {gauge_id} with key {key_label}: {he}")
        except Exception as e:
            print(f"[WARN] Error fetching USGS data for {gauge_id} with key {key_label}: {e}")
    return float("nan")


@app.route("/metrics")
def metrics():
    start_time = time.time()
    gauges = load_gauges()
    GAUGES_TOTAL.set(len(gauges))
    USGS_STREAMFLOW.clear()

    successes = 0
    failures = 0

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(gauges))) as executor:
        future_to_gauge = {executor.submit(fetch_usgs_gauge, g["id"]): g for g in gauges}
        for future in as_completed(future_to_gauge):
            g = future_to_gauge[future]
            gauge_id = g.get("id")
            friendly = g.get("friendly_name", g.get("name", gauge_id))
            location_name = g.get("name", gauge_id)

            try:
                val = future.result()
                if val != float("nan"):
                    successes += 1
                else:
                    failures += 1
            except Exception as e:
                print(f"[WARN] Error processing {gauge_id}: {e}")
                failures += 1
                val = float("nan")

            USGS_STREAMFLOW.labels(
                gauge_id=gauge_id,
                friendly_name=friendly,
                location_name=location_name
            ).set(val)

    SCRAPE_SUCCESS.set(successes)
    SCRAPE_FAILURE.set(failures)
    SCRAPE_DURATION.set(time.time() - start_time)

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
