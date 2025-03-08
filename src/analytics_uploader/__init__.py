import httpx
import dotenv
import os
from google.cloud import bigquery
from google.oauth2 import service_account
import io
import sys

dotenv.load_dotenv()

BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX = (
    "https://stage.rneventteknik.se/api/external/v1/analytics/"
)
BIG_QUERY_DATASET_ID = "rn-admin-391316.raw_backstage2"
DEFAULT_CREDENTIALS_PATH = "credentials.json"


def run_data_pipeline():
    booking_data = fetch_backstage2_raw_data(BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "bookings")
    equipment_usage_data = fetch_backstage2_raw_data(BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "equipmentUsage")
    time_report_data = fetch_backstage2_raw_data(BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "timeReports")
    push_data_to_big_query(booking_data, "booking")
    push_data_to_big_query(equipment_usage_data, "equipmentUsage")
    push_data_to_big_query(time_report_data, "timeReport")


def fetch_backstage2_raw_data(endpoint: str) -> str:
    print(f"Fetching data from endpoint: {endpoint}")
    with httpx.Client() as client:
        response = client.get(
            endpoint, headers={"X-API-KEY": os.environ["BACKSTAGE2_API_KEY"]}
        )
    return response.content


def push_data_to_big_query(data: str, table_name: str):
    table_id = f"{BIG_QUERY_DATASET_ID}.{table_name}"
    credentials_path = (
        sys.argv[1] if len(sys.argv) >= 2 else DEFAULT_CREDENTIALS_PATH
    )
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path
    )
    client = bigquery.Client(credentials=credentials)

    # Check if the table exists
    try:
        client.get_table(table_id)
        print(f"Table {table_id} already exists.")
    except Exception:
        print(f"Table {table_id} does not exist. Creating table...")

        job_config = bigquery.LoadJobConfig(
            autodetect=True,  # Infer schema
            source_format=bigquery.SourceFormat.CSV,
            field_delimiter=",",
            skip_leading_rows=1,
        )
        
        job = client.load_table_from_file(
            io.BytesIO(data), table_id, job_config=job_config
        )
        job.result()  # Wait for the table creation to complete
        print(f"Table {table_id} created successfully.")

    # Load data into the table
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.CSV,
        field_delimiter=",",
        skip_leading_rows=1,
    )
    job = client.load_table_from_file(
        io.BytesIO(data), table_id, job_config=job_config
    )
    job.result()  # Wait for the job to complete

    table_name = client.get_table(table_id)  # Fetch the updated table
    print(
        "Loaded {} rows and {} columns to {}".format(
            table_name.num_rows, len(table_name.schema), table_id
        )
    )
