"""Upload analytics data to BigQuery and initialize views."""

import argparse
import httpx
import dotenv
import os
from google.cloud import bigquery  # type: ignore
from google.oauth2 import service_account
import io
from googleapiclient.discovery import build

dotenv.load_dotenv()

BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX = (
    "https://stage.rneventteknik.se/api/external/v1/analytics/"
)
BIG_QUERY_DATASET_ID = "rn-admin-391316.raw_backstage2"
SPREADSHEET_DATASET_ID = "rn-admin-391316.raw_spreadsheet"
DEFAULT_CREDENTIALS_PATH = "credentials.json"
DEFAULT_SQL_DIRECTORY = "sql"
SPREADSHEET_DIRECTORY_ID = "1ESgH00-XT6mniJg11wAhwN-LXyXHzEde"


def process_sql_file(
    client: bigquery.Client, dataset_path: str, sql_file: str, dataset_id: str
):
    file_name = os.path.splitext(sql_file)[0]
    view_name = file_name.split("_")[1]
    view_id = f"{dataset_id}.{view_name}"
    print()
    print(f"Processing SQL file: {sql_file}")
    print(f"View ID: {view_id}")

    # Read the SQL query from file
    with open(os.path.join(dataset_path, sql_file), "r") as f:
        view_query = f.read()

    try:
        # Create or update the view
        view = bigquery.Table(view_id)
        view.view_query = view_query

        try:
            client.get_table(view_id)
            print(f"Trying to update view {view_id}...")
            client.update_table(view, ["view_query"])
            print(f"View {view_id} updated successfully.")
        except Exception as e:
            print(f"Error updating view {view_id}: {str(e)}")
            print(f"Creating view {view_id}...")
            client.create_table(view, exists_ok=True)
            print(f"View {view_id} created successfully.")

    except Exception as e:
        print(f"Error creating/updating view {view_id}: {str(e)}")


def process_dataset(client: bigquery.Client, dataset_name: str, dataset_path: str):
    dataset_id = f"{client.project}.{dataset_name}"

    # Create dataset if it doesn't exist
    try:
        client.get_dataset(dataset_id)
        print(f"Dataset {dataset_id} already exists.")
    except Exception:
        print(f"Creating dataset {dataset_id}...")
        dataset = bigquery.Dataset(dataset_id)
        client.create_dataset(dataset)

        # Process each SQL file as a view
    for sql_file in sorted(os.listdir(dataset_path)):
        if not sql_file.endswith(".sql"):
            continue
        process_sql_file(client, dataset_path, sql_file, dataset_id)


def initialize_views(credentials_path: str, sql_directory_path: str):
    credentials = service_account.Credentials.from_service_account_file(  # type: ignore
        credentials_path
    )
    client = bigquery.Client(credentials=credentials)
    if not os.path.exists(sql_directory_path):
        print(f"No SQL directory found at {sql_directory_path}")
        return

    # Process each dataset (subfolder)
    for dataset_name in os.listdir(sql_directory_path):
        dataset_path = os.path.join(sql_directory_path, dataset_name)
        if not os.path.isdir(dataset_path):
            continue
        process_dataset(client, dataset_name, dataset_path)


def fetch_backstage2_raw_data(endpoint: str) -> bytes:
    print(f"Fetching data from endpoint: {endpoint}")
    with httpx.Client() as client:
        response = client.get(
            endpoint, headers={"X-API-KEY": os.environ["BACKSTAGE2_API_KEY"]}
        )
    return response.content


def push_data_to_big_query(data: bytes, dataset_id: str,  table_name: str, credentials_path: str):
    table_id = f"{dataset_id}.{table_name}"
    credentials = service_account.Credentials.from_service_account_file(  # type: ignore
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
    job = client.load_table_from_file(io.BytesIO(data), table_id, job_config=job_config)
    job.result()  # Wait for the job to complete

    existing_table = client.get_table(table_id)  # Fetch the updated table
    print(
        "Loaded {} rows and {} columns to {}".format(
            existing_table.num_rows,
            len(existing_table.schema),  # type: ignore
            table_id,
        )
    )


def run_data_pipeline(credentials_path: str, sql_directory: str, run_steps: list[str] | None = None):
    # Default to running all steps if none specified
    if run_steps is None:
        run_steps = ["backstage", "sheets", "views"]

    if "backstage" in run_steps:
        booking_data = fetch_backstage2_raw_data(
            BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "bookings"
        )
        equipment_usage_data = fetch_backstage2_raw_data(
            BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "equipmentUsage"
        )
        time_report_data = fetch_backstage2_raw_data(
            BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "timeReports"
        )
        push_data_to_big_query(booking_data, BIG_QUERY_DATASET_ID, "booking", credentials_path)
        push_data_to_big_query(equipment_usage_data, BIG_QUERY_DATASET_ID, "equipmentUsage", credentials_path)
        push_data_to_big_query(time_report_data, BIG_QUERY_DATASET_ID, "timeReport", credentials_path)

    if "sheets" in run_steps:
        sheets_data = list_and_export_sheets_csv(
            SPREADSHEET_DIRECTORY_ID, credentials_path
        )
        for sheet_name, csv_data in sheets_data.items():
            if csv_data is not None:
                table_name = sheet_name.replace(" ", "_").lower()
                push_data_to_big_query(csv_data, SPREADSHEET_DATASET_ID, table_name, credentials_path)

    if "views" in run_steps:
        initialize_views(credentials_path, sql_directory)


def list_and_export_sheets_csv(folder_id, credentials_path="credentials.json"):
    """
    Lists all Google Sheets in the specified Google Drive folder and exports the first sheet of each as CSV (bytes).
    Args:
        folder_id (str): The ID of the Google Drive folder.
        credentials_path (str): Path to the service account credentials JSON file.
    Returns:
        dict: Mapping of spreadsheet name to its CSV content (as bytes).
    """
    print(f"Listing and exporting sheets from folder ID: {folder_id}")
    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    drive_service = build("drive", "v3", credentials=credentials)
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = (
        drive_service.files()
        .list(
            q=query,
            fields="files(id, name)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    files = results.get("files", [])
    csv_exports = {}
    for file in files:
        spreadsheet_id = file["id"]  # type: ignore
        name = file["name"]  # type: ignore
        print(f"Processing spreadsheet: {name} (ID: {spreadsheet_id})")
        try:
            # Export the first sheet as CSV (bytes)
            request = drive_service.files().export(
                fileId=spreadsheet_id, mimeType="text/csv"
            )
            csv_data = request.execute()
            csv_exports[name] = csv_data  # Keep as bytes
        except Exception:
            csv_exports[name] = None
    return csv_exports


def main():
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument(
        "-c",
        "--credentials",
        type=str,
        help="Path to the credentials JSON file.",
        default=DEFAULT_CREDENTIALS_PATH,
    )
    argparser.add_argument(
        "-s",
        "--sql-directory",
        type=str,
        help="Path to the directory with SQL files to initialize view."
        " Should contain subfolders for each dataset and the filenames"
        " should be on the format <initiation order index>_<SQL view name>.sql.",
        default=DEFAULT_SQL_DIRECTORY,
    )
    argparser.add_argument(
        "--run-steps",
        nargs="*",
        choices=["backstage", "sheets", "views"],
        help="Specify which pipeline steps to run. Options: backstage (Backstage2 data), "
        "sheets (Google Sheets data), views (BigQuery views). If not specified, all steps run.",
    )
    args = argparser.parse_args()
    run_data_pipeline(args.credentials, args.sql_directory, args.run_steps)
