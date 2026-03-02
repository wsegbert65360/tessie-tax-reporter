import os
import json
from dotenv import load_dotenv
from tessie_api import TessieClient

load_dotenv()
api_token = os.getenv("TESSIE_API_TOKEN")
client = TessieClient(api_token)

vehicles = client.get_vehicles()
if vehicles:
    vin = vehicles[0]['vin']
    print(f"Checking VIN: {vin}")
    drives = client.get_drives(vin)
    if drives:
        print("Keys in drive object:")
        print(list(drives[0].keys()))
        print("\nSample values:")
        for k in ['starting_odometer', 'ending_odometer', 'start_odometer', 'end_odometer', 'starting_odo', 'ending_odo', 'odometer']:
            if k in drives[0]:
                print(f"{k}: {drives[0][k]}")
    else:
        print("No drives found.")
else:
    print("No vehicles found.")
