#!/usr/bin/env bash
# One-time setup script for deploying analytics-uploader as a Cloud Run Job.
# Run once as a project owner with gcloud authenticated to rn-admin-391316.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - BACKSTAGE2_API_KEY exported in your shell
#   - credentials.json present in the current working directory
#   - GITHUB_OWNER set to your GitHub username/org (e.g. "myorg")
#
# Usage:
#   export BACKSTAGE2_API_KEY="your-api-key"
#   export GITHUB_OWNER="your-github-owner"
#   cd /path/to/analytics-uploader
#   bash gcp/setup.sh

set -euo pipefail

PROJECT=rn-admin-391316
REGION=europe-west1
RUNNER_SA=analytics-uploader-runner@${PROJECT}.iam.gserviceaccount.com
SCHEDULER_SA=analytics-uploader-scheduler@${PROJECT}.iam.gserviceaccount.com
CICD_SA=analytics-uploader-cicd@${PROJECT}.iam.gserviceaccount.com

# --- Validate prerequisites ---
if [[ -z "${BACKSTAGE2_API_KEY:-}" ]]; then
  echo "ERROR: BACKSTAGE2_API_KEY is not set. Export it before running this script."
  exit 1
fi

if [[ -z "${GITHUB_OWNER:-}" ]]; then
  echo "ERROR: GITHUB_OWNER is not set. Export it before running this script."
  exit 1
fi

if [[ ! -f credentials.json ]]; then
  echo "ERROR: credentials.json not found in the current directory."
  exit 1
fi

echo "=== Section 1: Enable APIs ==="
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  --project=${PROJECT}

echo "=== Section 2: Create secrets ==="
gcloud secrets create backstage2-api-key \
  --replication-policy=automatic \
  --project=${PROJECT}
echo -n "${BACKSTAGE2_API_KEY}" | gcloud secrets versions add backstage2-api-key \
  --data-file=- \
  --project=${PROJECT}

gcloud secrets create analytics-uploader-credentials \
  --replication-policy=automatic \
  --project=${PROJECT}
gcloud secrets versions add analytics-uploader-credentials \
  --data-file=credentials.json \
  --project=${PROJECT}

echo "=== Section 3: Create service accounts and IAM bindings ==="

# Runtime SA
gcloud iam service-accounts create analytics-uploader-runner \
  --display-name="Analytics Uploader - Runtime" \
  --project=${PROJECT}

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:${RUNNER_SA}" \
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:${RUNNER_SA}" \
  --role="roles/bigquery.jobUser"

gcloud secrets add-iam-policy-binding backstage2-api-key \
  --member="serviceAccount:${RUNNER_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=${PROJECT}
gcloud secrets add-iam-policy-binding analytics-uploader-credentials \
  --member="serviceAccount:${RUNNER_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=${PROJECT}

# Scheduler SA
gcloud iam service-accounts create analytics-uploader-scheduler \
  --display-name="Analytics Uploader - Scheduler" \
  --project=${PROJECT}

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role="roles/run.invoker"

# CI/CD SA
gcloud iam service-accounts create analytics-uploader-cicd \
  --display-name="Analytics Uploader - CI/CD" \
  --project=${PROJECT}

gcloud projects add-iam-policy-binding ${PROJECT} \
  --member="serviceAccount:${CICD_SA}" \
  --role="roles/run.developer"

echo "=== Section 4: Create Cloud Run Job ==="
gcloud run jobs create analytics-uploader \
  --image="ghcr.io/${GITHUB_OWNER}/analytics-uploader:latest" \
  --region=${REGION} \
  --service-account=${RUNNER_SA} \
  --set-secrets=BACKSTAGE2_API_KEY=backstage2-api-key:latest \
  --set-secrets=/app/credentials.json=analytics-uploader-credentials:latest \
  --max-retries=0 \
  --task-timeout=3600 \
  --project=${PROJECT}

echo "=== Section 5: Create Cloud Scheduler job ==="
gcloud scheduler jobs create http analytics-uploader-daily \
  --location=${REGION} \
  --schedule="0 3 * * *" \
  --time-zone="Europe/Stockholm" \
  --uri="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/analytics-uploader:run" \
  --http-method=POST \
  --oauth-service-account-email=${SCHEDULER_SA} \
  --project=${PROJECT}

echo "=== Section 6: Export CI/CD key ==="
gcloud iam service-accounts keys create /tmp/cicd-key.json \
  --iam-account=${CICD_SA} \
  --project=${PROJECT}

echo ""
echo "=== ACTION REQUIRED ==="
echo "Add the contents of /tmp/cicd-key.json as the GitHub secret GCP_SA_KEY:"
echo "  https://github.com/${GITHUB_OWNER}/analytics-uploader/settings/secrets/actions"
echo "Then delete /tmp/cicd-key.json"
echo ""
cat /tmp/cicd-key.json
