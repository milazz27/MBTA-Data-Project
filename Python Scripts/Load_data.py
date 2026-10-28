import os
import requests
from dotenv import load_dotenv

load_dotenv()
"""
GLOBAL VARIABLES
"""
DATA_KEY = os.environ["MBTA_DATA_KEY"]
BASE_URL = "https://api-v3.mbta.com"

def get_stops(params: dict) -> list[dict]:
    """
    @brief: makes requests to access data on stops information with
        given parameters
    
    @ param: params: dictionary of parameters to pass into request
    @return: a list of dictionary-formatted responses
    """

    response = requests.get(
        f"{BASE_URL}/stops",
        headers={"x-api-key": DATA_KEY},
        params=params,
        timeout=10,
        )
    response.raise_for_status()
    print("Remaining:", response.headers.get("x-ratelimit-remaining"))
    return response.json()["data"]

if __name__ == "__main__":
    stops_params = {
        "filter[route]": "Red",
        "fields[stop]": "name,latitude,longitude"
        }
    stops = get_stops(stops_params)

    for s in stops[:5]:
        print(s["id"], s["attributes"]["name"])