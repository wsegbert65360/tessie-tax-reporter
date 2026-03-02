import requests
import os
import logging
import time

logger = logging.getLogger(__name__)

class TessieClient:
    BASE_URL = "https://api.tessie.com"

    def __init__(self, api_token):
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json"
        })

    def _request(self, method, url, **kwargs):
        """Internal helper to handle requests with retry logic for rate limits."""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code == 429:
                    logger.warning(f"Rate limit hit for {url}. Attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
                retry_delay *= 2
        return None

    def get_vehicles(self):
        """Fetch all vehicles associated with the account."""
        url = f"{self.BASE_URL}/vehicles"
        data = self._request("GET", url)
        return data.get('results', []) if data else []

    def get_drives(self, vin, start_date=None, end_date=None):
        """Fetch drives for a specific vehicle."""
        url = f"{self.BASE_URL}/{vin}/drives"
        params = {}
        if start_date:
            params['from'] = start_date
        if end_date:
            params['to'] = end_date

        data = self._request("GET", url, params=params)
        return data.get('results', []) if data else []
