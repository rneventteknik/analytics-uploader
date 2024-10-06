import httpx
import dotenv
import os
from google.cloud import bigquery
from google.oauth2 import service_account
import io
import sys

dotenv.load_dotenv()

BACKSTAGE2_ENDPOINT = (
    "https://stage.rneventteknik.se/api/external/v1/analytics/bookings"
)
BIG_QUERY_TABLE_ID = "rn-admin-391316.raw_backstage2.booking"
DEFAULT_CREDENTIALS_PATH = "credentials.json"


def run_data_pipeline():
    data = fetch_backstage2_raw_data()
    push_data_to_big_query(data)


def fetch_backstage2_raw_data() -> str:
    with httpx.Client() as client:
        response = client.get(
            BACKSTAGE2_ENDPOINT, headers={"X-API-KEY": os.environ["BACKSTAGE2_API_KEY"]}
        )
    return response.content


def push_data_to_big_query(data: str):
    credentials_path = (
        sys.argv.get(1) if sys.argv[1] is not None else DEFAULT_CREDENTIALS_PATH
    )
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path
    )
    client = bigquery.Client(credentials=credentials)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.CSV,
        field_delimiter=",",
        skip_leading_rows=1,
    )
    job = client.load_table_from_file(
        io.BytesIO(data), BIG_QUERY_TABLE_ID, job_config=job_config
    )

    job.result()  # Waits for the job to complete.

    table = client.get_table(BIG_QUERY_TABLE_ID)  # Make an API request.
    print(
        "Loaded {} rows and {} columns to {}".format(
            table.num_rows, len(table.schema), BIG_QUERY_TABLE_ID
        )
    )
