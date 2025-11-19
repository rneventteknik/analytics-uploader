# analytics-uploader
A service that downloads Backstage2 data and uploads it to Google BigQuery daily.

Built using Python by the RN analytics team.

## Environment variables
Can be added to `.env` file.

```
BACKSTAGE2_API_KEY={the api key}
```

## Usage Examples

Run the entire pipeline (uses `credentials.json` and `sql/` directory):
```bash
analytics-uploader
```

Run only Google Sheets data upload:
```bash
analytics-uploader --run-steps sheets
```

Run only Backstage2 data:
```bash
analytics-uploader --run-steps backstage
```

Run sheets and update views (skip Backstage2):
```bash
analytics-uploader --run-steps sheets views
```

Run all steps explicitly:
```bash
analytics-uploader --run-steps backstage sheets views
```

## Running with Docker

### Using Docker Compose

1. Create a `.env` file with your environment variables:
```bash
BACKSTAGE2_API_KEY=your-api-key
```

2. Ensure `credentials.json` (Google service account) is in the project root

3. Run the service:
```bash
docker-compose up
```

### Using Docker CLI

Build and run locally:
```bash
docker build -t analytics-uploader .

docker run \
  -v ./credentials.json:/app/credentials.json:ro \
  -e BACKSTAGE2_API_KEY="your-api-key" \
  analytics-uploader \
  -c /app/credentials.json
```

### Using Published Image from GHCR

Pull from GitHub Container Registry:
```bash
docker pull ghcr.io/rneventteknik/analytics-uploader:latest

docker run \
  -v ./credentials.json:/app/credentials.json:ro \
  -e BACKSTAGE2_API_KEY="your-api-key" \
  ghcr.io/rneventteknik/analytics-uploader:latest \
  -c /app/credentials.json -s /app/sql
```
