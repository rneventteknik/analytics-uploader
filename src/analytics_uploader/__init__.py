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

def initializeViews():
    credentials_path = sys.argv[1] if len(sys.argv) >= 2 else DEFAULT_CREDENTIALS_PATH
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    client = bigquery.Client(credentials=credentials)
    
    # Get the base directory (where src and sql folders are)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sql_dir = os.path.join(base_dir, 'sql')
    
    if not os.path.exists(sql_dir):
        print(f"No SQL directory found at {sql_dir}")
        return
    
    # Process each dataset (subfolder)
    for dataset_name in os.listdir(sql_dir):
        dataset_path = os.path.join(sql_dir, dataset_name)
        if not os.path.isdir(dataset_path):
            continue
            
        dataset_id = f"{client.project}.{dataset_name}"
        
        # Create dataset if it doesn't exist
        try:
            client.get_dataset(dataset_id)
            print(f"Dataset {dataset_id} already exists.")
        except Exception:
            print(f"Creating dataset {dataset_id}...")
            dataset = bigquery.Dataset(dataset_id)
            client.create_dataset(dataset, exists_ok=True)
            
        # Process each SQL file as a view
        for sql_file in os.listdir(dataset_path):
            if not sql_file.endswith('.sql'):
                continue
                
            view_name = os.path.splitext(sql_file)[0]
            view_id = f"{dataset_id}.{view_name}"
            
            # Read the SQL query from file
            with open(os.path.join(dataset_path, sql_file), 'r') as f:
                view_query = f.read()
            
            try:
                # Create or update the view
                view = bigquery.Table(view_id)
                view.view_query = view_query
                
                try:
                    client.get_table(view_id)
                    print(f"Updating view {view_id}...")
                    client.update_table(view, ['view_query'])
                except Exception:
                    print(f"Creating view {view_id}...")
                    client.create_table(view)
                    
            except Exception as e:
                print(f"Error creating/updating view {view_id}: {str(e)}")

def run_data_pipeline():
    booking_data = fetch_backstage2_raw_data(BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "bookings")
    equipment_usage_data = fetch_backstage2_raw_data(BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "equipmentUsage")
    time_report_data = fetch_backstage2_raw_data(BACKSTAGE2_ANALYTICS_ENDPOINT_PREFIX + "timeReports")
    push_data_to_big_query(booking_data, "booking")
    push_data_to_big_query(equipment_usage_data, "equipmentUsage")
    push_data_to_big_query(time_report_data, "timeReport")
    initializeViews()


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
