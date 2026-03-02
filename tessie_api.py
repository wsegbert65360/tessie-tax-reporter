import requests
import os

class TessieClient:
    BASE_URL = "https://api.tessie.com"

    def __init__(self, api_token):
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json"
        })

    def get_vehicles(self):
        """Fetch all vehicles associated with the account."""
        url = f"{self.BASE_URL}/vehicles"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('results', [])

    def get_drives(self, vin, start_date=None, end_date=None):
        """
        Fetch drives for a specific vehicle.
        
        Args:
            vin (str): Vehicle Identification Number
            start_date (str, optional): Start date (Unix timestamp or some format depending on API, usually unix)
            end_date (str, optional): End date
        """
        url = f"{self.BASE_URL}/{vin}/drives"
        params = {}
        # Tessie API typically accepts 'interval', or specific range parameters if using their history endpoints.
        # The standardized /drives endpoint usually returns recent drives. 
        # For historical data, we might need to iterate or use specific params if documented.
        # Assuming standard 'from' and 'to' timestamp usage if supported, or just fetching the default page.
        # Let's start with basic fetching.
        
        if start_date:
            params['from'] = start_date
        if end_date:
            params['to'] = end_date

        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('results', [])
