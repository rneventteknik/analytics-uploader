import httpx
import dotenv
import os

dotenv.load_dotenv()

BACKSTAGE2_ENDPOINT = "https://stage.rneventteknik.se/api/external/v1/analytics/bookings"

def hello_world():
    print("hello world")

def fetch_backstage2_raw_data():
    with httpx.Client() as client:
        response = client.get(BACKSTAGE2_ENDPOINT, headers={"X-API-KEY": os.environ["BACKSTAGE2_API_KEY"]})
    print(response.content)