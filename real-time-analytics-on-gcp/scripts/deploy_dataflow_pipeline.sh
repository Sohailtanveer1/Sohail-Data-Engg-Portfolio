#!/usr/bin/env bash
# Builds the Flex Template image (via Cloud Build, so no local Docker
# daemon is required), stages the template spec, and launches/updates the
# streaming job. Called by hand for now; .github/workflows/cd-dev.yml
# calls this same script in CI once you're past Phase 10.
#
# Job name is fixed as supplychain-streaming-<environment> — this MUST
# match infra/terraform/environments/<env>/main.tf's
# local.dataflow_job_name, since the monitoring module's alert policies
# filter on that exact job name.
set -euo pipefail

ENVIRONMENT="${1:?usage: deploy_dataflow_pipeline.sh <dev|uat|prod>}"
PROJECT_ID="${PROJECT_ID:?set PROJECT_ID env var}"
REGION="${REGION:-us-east1}"
# Zone is left empty by default so Dataflow auto-selects an available zone
# within REGION (avoids a hardcoded zone that could be exhausted or, worse,
# not exist in the chosen region). Pin one only if you need to — e.g.
# WORKER_ZONE=us-east1-b — and make sure it belongs to REGION.
WORKER_ZONE="${WORKER_ZONE:-}"
# e2-standard-2 is smaller than the Dataflow default (n1-standard-4) — more
# widely available when a zone is tight on the older n1 family, and cheaper,
# which suits a free trial.
WORKER_MACHINE_TYPE="${WORKER_MACHINE_TYPE:-e2-standard-2}"
PIPELINE_VERSION="$(git rev-parse --short HEAD)"

JOB_NAME="supplychain-streaming-${ENVIRONMENT}"
REPO="supplychain-dataflow-${ENVIRONMENT}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/streaming-pipeline:${PIPELINE_VERSION}"
TEMPLATE_SPEC_GCS="gs://${PROJECT_ID}-dataflow-staging-${ENVIRONMENT}/templates/streaming-pipeline-${PIPELINE_VERSION}.json"
STAGING_BUCKET="${PROJECT_ID}-dataflow-staging-${ENVIRONMENT}"
RAW_ARCHIVE_BUCKET="${PROJECT_ID}-raw-event-archive-${ENVIRONMENT}"
WORKER_SA="sa-dataflow-worker-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
SUBNET="regions/${REGION}/subnetworks/supplychain-${ENVIRONMENT}-subnet"

echo "== Building image ${IMAGE} via Cloud Build =="
gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config dataflow/pipelines/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}" \
  .

echo "== Building Flex Template spec at ${TEMPLATE_SPEC_GCS} =="
gcloud dataflow flex-template build "${TEMPLATE_SPEC_GCS}" \
  --project "${PROJECT_ID}" \
  --image "${IMAGE}" \
  --sdk-language PYTHON \
  --metadata-file dataflow/pipelines/metadata.json

# --update requires a running job with this exact name already in place
# (Dataflow's in-place pipeline update); the first-ever deploy for an
# environment has nothing to update against, so it must launch fresh.
UPDATE_FLAG=()
if gcloud dataflow jobs list --project "${PROJECT_ID}" --region "${REGION}" \
     --filter="name=${JOB_NAME} AND STATE=Running" --format="value(name)" | grep -q "${JOB_NAME}"; then
  echo "Existing running job found — deploying as an in-place update."
  UPDATE_FLAG=(--update)
else
  echo "No running job named ${JOB_NAME} — launching fresh."
fi

# Only pass --worker-zone when a zone is explicitly set; otherwise let
# Dataflow pick an available zone in REGION.
ZONE_FLAG=()
if [[ -n "${WORKER_ZONE}" ]]; then
  ZONE_FLAG=(--worker-zone "${WORKER_ZONE}")
fi

echo "== Launching/updating job ${JOB_NAME} =="
gcloud dataflow flex-template run "${JOB_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --template-file-gcs-location "${TEMPLATE_SPEC_GCS}" \
  --staging-location "gs://${STAGING_BUCKET}/staging" \
  --temp-location "gs://${STAGING_BUCKET}/temp" \
  --service-account-email "${WORKER_SA}" \
  --subnetwork "${SUBNET}" \
  --disable-public-ips \
  "${ZONE_FLAG[@]}" \
  --worker-machine-type "${WORKER_MACHINE_TYPE}" \
  --launcher-machine-type "${WORKER_MACHINE_TYPE}" \
  --max-workers 2 \
  --parameters project="${PROJECT_ID}",environment="${ENVIRONMENT}",raw_archive_bucket="${RAW_ARCHIVE_BUCKET}",pipeline_version="${PIPELINE_VERSION}",sdk_container_image="${IMAGE}" \
  "${UPDATE_FLAG[@]}"

# NOTE: sdk_container_image above is a standard Beam pipeline option (Beam
# maps it to WorkerOptions), passed through --parameters because the pipeline
# forwards unknown args to PipelineOptions. It makes the workers run our
# dual-purpose image (which has the pipeline code + deps) instead of the
# stock Beam SDK container — required, or workers crash on import.

echo "== Done. Job: ${JOB_NAME} (version ${PIPELINE_VERSION}) =="
