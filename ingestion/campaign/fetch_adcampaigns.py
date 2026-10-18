import json
import logging
import os
import time
import pandas as pd
from load_campaigns import load_campaigns

import requests


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

URL = "http://localhost:8000/v1/campaigns"

# Read the secret from outside the code - no default for secrets
token = os.getenv("AD_API_TOKEN")  # AD_API_TOKEN is passed as variable value in the command line, e.g. AD_API_TOKEN=... python fetch_adcampaigns.py

if not token:
    raise RuntimeError("AD_API_TOKEN is not set. Run: AD_API_TOKEN=... python fetch_adcampaigns.py")


def fetch_page(url, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            response.raise_for_status()      # turns 4xx/5xx into an error
            return response.json()

        except requests.exceptions.RequestException as e:
            status = e.response.status_code if e.response is not None else None

            # 401, 403, 404: no point retrying
            if status is not None and status < 500 and status != 429:
                log.error(f"Permanent error {status} - not retrying")
                raise

            log.warning(f"Attempt {attempt} of {max_retries} failed: {e}")
            
            if attempt == max_retries:
                log.error(f"Giving up after {max_retries} attempts")
                raise

            # how long to wait using retry-after header if present, otherwise exponential backoff
            if status == 429:
                wait = int(e.response.headers.get("Retry-After", 2 ** attempt))
                log.warning(f"Rate limited. Waiting {wait} seconds as provided by Retry-After header from api")
            else:
                wait = 2 ** attempt # exponential backoff: wait 2s, then 4s, then 8s
            time.sleep(wait)


url = URL  #initial URL to fetch the first page of campaigns
all_campaigns = [] #empty list to hold all campaigns fetched from the API

while url:
    body = fetch_page(url)
    all_campaigns.extend(body["data"])
    log.info(f"Fetched {len(body['data'])} campaigns (total so far {len(all_campaigns)})")
    url = body["paging"].get("next")

log.info(f"Done: {len(all_campaigns)} campaigns in total")

df = pd.DataFrame({
    "id":      [c["id"] for c in all_campaigns],
    "payload": [json.dumps(c) for c in all_campaigns],   # exactly as the API sent it
   })
df["loaded_at"] = pd.Timestamp.now(tz="UTC")

load_campaigns(df)  # call the load_campaigns function to load the data into the database