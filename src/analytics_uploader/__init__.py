"""Upload analytics data to BigQuery and initialize views."""

import argparse
import csv
import time
import httpx
import dotenv
import os
from google.cloud import bigquery  # type: ignore
from google.oauth2 import service_account
import io
from googleapiclient.discovery import build

dotenv.load_dotenv()

BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX = os.environ.get(
    "BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX",
    "https://stage.rneventteknik.se/api/external/v1/analytics/",
)
BIG_QUERY_DATASET_ID = "rn-admin-391316.raw_backstage2"
SPREADSHEET_DATASET_ID = "rn-admin-391316.raw_spreadsheet"
DEFAULT_CREDENTIALS_PATH = "credentials.json"
DEFAULT_SQL_DIRECTORY = "sql"
SPREADSHEET_DIRECTORY_ID = "1ESgH00-XT6mniJg11wAhwN-LXyXHzEde"
# Number of bookings to request per Backstage2 analytics page. The endpoints
# paginate by booking; we page through all of them so this only controls request size.
PAGE_SIZE = 100
# Seconds to wait between successive page requests, to avoid loading the server.
REQUEST_DELAY_SECONDS = 0.5


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


def min_booking_id(csv_text: str, booking_id_column: str) -> int | None:
    """Smallest booking id in a CSV page, resolved by header name (None if no ids).

    Must be resolved by name, not position: for `equipmentUsage`/`timeReports` the first
    column is the entry id, not the booking id.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    ids = (int(row[booking_id_column]) for row in reader if row[booking_id_column])
    return min(ids, default=None)


def iter_backstage2_pages(
    client: httpx.Client,
    endpoint: str,
    headers: dict[str, str],
    booking_id_column: str,
    page_size: int,
):
    """Yield non-empty CSV page bodies, walking backwards over every booking id.

    The endpoints paginate by booking via `pageSize`/`maxBookingId` and order rows by
    booking id descending. Each step sets `maxBookingId = (smallest id seen) - 1` to walk
    from the newest booking to the oldest with no overlap and no gaps.
    """
    max_booking_id: int | None = None
    while True:
        params: dict[str, int] = {"pageSize": page_size}
        if max_booking_id is not None:
            params["maxBookingId"] = max_booking_id
            # Throttle every request after the first to avoid loading the server.
            time.sleep(REQUEST_DELAY_SECONDS)

        response = client.get(endpoint, params=params, headers=headers)
        response.raise_for_status()
        text = response.text

        # A page can return fewer rows than `page_size` -- the server applies the
        # `pageSize` limit when querying the DB, then filters out internal-reservation
        # bookings afterwards. So a page covers `page_size` booking ids but may yield
        # fewer (or, if the whole window was internal reservations, zero) data rows.
        if not text.strip():
            # Empty page. A full window of bookings can be filtered out server-side even
            # though older real bookings still exist, so keep walking down rather than
            # stopping immediately (Option B). A first empty page means no data at all.
            if max_booking_id is None:
                return
            max_booking_id -= page_size
            if max_booking_id < 1:
                return
            continue

        yield text

        smallest = min_booking_id(text, booking_id_column)
        if smallest is None or smallest <= 1:
            return
        max_booking_id = smallest - 1


def fetch_backstage2_raw_data(
    endpoint: str, booking_id_column: str, page_size: int = PAGE_SIZE
) -> bytes:
    """Page through a paginated Backstage2 analytics endpoint and reassemble the full CSV.

    Concatenates every page into a single CSV: the header is taken from the first page
    only, then all data rows from every page are appended.
    """
    print(f"Fetching data from endpoint: {endpoint}")
    headers = {"X-API-KEY": os.environ["BACKSTAGE2_API_KEY"]}

    with httpx.Client(timeout=120.0) as client:
        pages = list(
            iter_backstage2_pages(
                client, endpoint, headers, booking_id_column, page_size
            )
        )

    if not pages:
        return b""

    header_line = pages[0].splitlines()[0]
    data_rows = [row for page in pages for row in page.splitlines()[1:]]

    print(f"Fetched {len(data_rows)} data rows from endpoint: {endpoint}")
    return "\r\n".join([header_line, *data_rows]).encode("utf-8")


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
            BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "bookings", "id"
        )
        equipment_usage_data = fetch_backstage2_raw_data(
            BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "equipmentUsage", "bookingId"
        )
        time_report_data = fetch_backstage2_raw_data(
            BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "timeReports", "bookingId"
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
        except Exception as e:
            print(e)
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
