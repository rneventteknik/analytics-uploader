# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**analytics-uploader** is a Python ETL service for the RN (RN Eventteknik) analytics team. It automates daily downloads of event booking data from the Backstage2 system and Google Sheets, then uploads to Google BigQuery for analytics and reporting.

- **Single-file architecture**: Main logic in `src/analytics_uploader/__init__.py` (241 lines)
- **Deployment**: Runs as a systemd service on Linux, scheduled daily at midnight (Europe/Stockholm)
- **Data flow**: Backstage2 API + Google Sheets → BigQuery raw tables → SQL views for analytics

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip3 install -r requirements.txt

# Install package in editable mode
pip3 install -e .

# Configure environment
# Create .env file with:
#   BACKSTAGE2_API_KEY=<your-key>
#   SPREADSHEETS_FOLDER_ID=<google-drive-folder-id>
# Add credentials.json (Google service account with drive.readonly, spreadsheets.readonly scopes)
```

### Running Locally
```bash
# Run with defaults (credentials.json, sql/ directory)
analytics-uploader

# Run with custom paths
analytics-uploader -c /path/to/credentials.json -s /path/to/sql/

# Alternative execution
python -m analytics_uploader
```

### Production Deployment
```bash
# Install as systemd service (Linux only, requires root)
cd environment/
sudo ./install.sh

# Service management
systemctl start rn.analytics-uploader.service    # Manual trigger
systemctl status rn.analytics-uploader.timer     # Check schedule
journalctl -u rn.analytics-uploader.service      # View logs
journalctl -u rn.analytics-uploader.service -f   # Follow logs
```

### Testing
⚠️ **No testing infrastructure exists.** There are no test files, test runners, or CI/CD pipelines. Test changes manually before deploying.

## Architecture

### ETL Pipeline Pattern
The service follows a three-phase ETL pipeline in `run_data_pipeline()`:

1. **Extract**: Fetch data from multiple sources
   - Backstage2 API endpoints: `/analytics/bookings`, `/analytics/equipmentUsage`, `/analytics/timeReports`
   - Google Sheets: Export all sheets in configured Drive folder as CSV

2. **Load**: Push raw CSV data to BigQuery
   - Tables created in `rn-admin-391316.raw_backstage2` dataset
   - Spreadsheet tables in `rn-admin-391316.raw_spreadsheet` dataset
   - Uses `WRITE_TRUNCATE` strategy (full refresh on each run)
   - Auto-creates tables with schema inference on first load

3. **Transform**: Create/update BigQuery views from SQL files
   - Views created in `calculated` dataset
   - SQL files in `sql/calculated/` directory

### Key Components

- **`fetch_backstage2_raw_data(endpoint)`**: HTTP GET with API key authentication
- **`list_and_export_sheets_csv(folder_id)`**: Google Drive API integration for sheet exports
- **`push_data_to_big_query()`**: Handles table creation and data loading
- **`initialize_views()`**: Processes SQL directory structure to create views
- **`process_dataset()`**: Creates dataset and all views within it
- **`process_sql_file()`**: Creates or updates individual BigQuery views

### Data Sources and Destinations

**Hardcoded BigQuery Configuration:**
- Project: `rn-admin-391316`
- Raw data datasets: `raw_backstage2`, `raw_spreadsheet`
- Calculated dataset: `calculated`
- ⚠️ These are hardcoded in the source - changes require code modification

**Backstage2 API:**
- Endpoint: `https://stage.rneventteknik.se/api/external/v1/`
- Authentication: X-API-KEY header from `BACKSTAGE2_API_KEY` env var
- Returns CSV data

**Google Sheets:**
- Access via Drive API v3 and Sheets API
- Authentication: Service account JSON (credentials.json)
- Required scopes: `drive.readonly`, `spreadsheets.readonly`

## Important Conventions

### SQL View Naming
SQL files in `sql/calculated/` must follow this naming pattern:
```
<number>_<view_name>.sql
```
- The **number prefix** determines view creation order
- The **view_name** becomes the actual BigQuery view name
- Example: `1_revenue.sql` creates view named `revenue`

This ordering is important because views may depend on other views.

### Spreadsheet Table Naming
Google Sheets are converted to BigQuery tables using:
- Sheet title converted to lowercase
- Spaces replaced with underscores
- Example: "Equipment Report" → `equipment_report` table

### Data Refresh Strategy
- **WRITE_TRUNCATE** mode: All tables are completely replaced on each run
- No incremental updates or CDC (Change Data Capture)
- Safe to re-run - operations are idempotent
- Historical data must be preserved in BigQuery (not in source tables)

### Business Context
- Swedish event management system (THS - likely KTH student union)
- Revenue tracking for equipment rentals and time reports
- Fiscal year calculations
- Integration with Hogia invoice system
- Status field "Klar" (Swedish for "Done") indicates completed bookings
- Revenue only counted for non-fixed-price, completed bookings

## Configuration Files

### Environment Variables (.env)
```bash
BACKSTAGE2_API_KEY=<api-key>           # Backstage2 API authentication
SPREADSHEETS_FOLDER_ID=<folder-id>     # Google Drive folder containing sheets
```

### Google Service Account (credentials.json)
- Not in version control (in .gitignore)
- Must have Drive and Sheets readonly permissions
- Required for production and local development

### SystemD Service Files (environment/)
- `rn.analytics-uploader.service`: Service definition
- `rn.analytics-uploader.timer`: Daily schedule (00:00 Europe/Stockholm)
- `install.sh`: Installation script (copies files, enables timer)

## Common Development Tasks

### Adding a New Backstage2 Data Source
1. Add new fetch call in `run_data_pipeline()`:
   ```python
   new_data = fetch_backstage2_raw_data("newEndpoint")
   ```
2. Add to data dictionary passed to `push_data_to_big_query()`
3. Table will auto-create in `raw_backstage2` dataset

### Adding a New BigQuery View
1. Create SQL file in `sql/calculated/` with numbered prefix:
   ```
   sql/calculated/4_myNewView.sql
   ```
2. Number determines creation order (important if view depends on others)
3. View will auto-create on next run

### Changing the Schedule
Edit `environment/rn.analytics-uploader.timer`:
```ini
[Timer]
OnCalendar=00:00:00  # Modify this line
Persistent=true
```
Then reinstall: `cd environment/ && sudo ./install.sh`

### Debugging Production Issues
```bash
# View recent logs
journalctl -u rn.analytics-uploader.service -n 100

# Follow logs in real-time
journalctl -u rn.analytics-uploader.service -f

# Trigger manual run
systemctl start rn.analytics-uploader.service

# Check timer status
systemctl list-timers | grep analytics-uploader
```

## Gotchas and Limitations

- **No error handling**: API failures will crash the service (logs to systemd journal)
- **No retry logic**: Failed runs must be manually triggered
- **No data validation**: Relies on schema inference and BigQuery's error handling
- **Hardcoded dataset IDs**: Changing GCP project/datasets requires code changes
- **Root user**: Production service runs as root (security consideration)
- **Full refresh only**: No support for incremental updates
- **No monitoring**: No alerts or notifications on failure
- **Missing tests**: All changes must be tested manually
