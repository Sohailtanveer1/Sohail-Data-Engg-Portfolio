# Dual-purpose image: works BOTH as the Flex Template launcher (via the
# launcher binary copied from the launcher base) AND as the Dataflow worker
# SDK container (FROM the Beam SDK base). This is the key fix for the
# "SDK harness disconnected" worker crash: the workers must run an image
# that actually contains supplychain_common, the transform modules, and
# their deps (jsonschema, etc.). The stock beam_python SDK container has
# none of that. The deploy script sets --sdk_container_image to this image
# so workers use it instead of the stock one.
FROM apache/beam_python3.11_sdk:2.57.0

# Lift the Flex Template launcher binary out of the launcher base image so
# this single image can also serve as the template launcher.
COPY --from=gcr.io/dataflow-templates-base/python311-template-launcher-base \
     /opt/google/dataflow/python_template_launcher \
     /opt/google/dataflow/python_template_launcher

ARG WORKDIR=/template
WORKDIR ${WORKDIR}

COPY dataflow/pipelines/ ${WORKDIR}/dataflow/pipelines/
COPY dataflow/transforms/ ${WORKDIR}/dataflow/transforms/
COPY common/ ${WORKDIR}/common/
# The JSON Schemas the validator loads at runtime. schema_validator.py
# resolves them relative to the repo layout (parents[2]/kafka/schemas), so
# they must sit at /template/kafka/schemas for both launcher and workers.
COPY kafka/schemas/ ${WORKDIR}/kafka/schemas/

ENV FLEX_TEMPLATE_PYTHON_PY_FILE="${WORKDIR}/dataflow/pipelines/streaming_pipeline.py"
# Runtime requirements = the cleaned, editable-free file baked below.
ENV FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE="${WORKDIR}/requirements-runtime.txt"
# Put the transforms and common dirs on the path directly, so the pipeline's
# bare imports (`import add_audit_columns`, `import supplychain_common`)
# resolve on the WORKERS too — not just the launcher. The pipeline's own
# sys.path.insert calls only run at construction time; the workers need the
# paths set in the environment to import the pickled DoFns' modules.
ENV PYTHONPATH="${WORKDIR}:${WORKDIR}/dataflow/transforms:${WORKDIR}/common"

RUN pip install --no-cache-dir --upgrade pip \
    && grep -v '^-e' ${WORKDIR}/dataflow/pipelines/requirements.txt > ${WORKDIR}/requirements-runtime.txt \
    && pip install --no-cache-dir -r ${WORKDIR}/requirements-runtime.txt \
    # Installs supplychain_common AND its declared deps (jsonschema) so both
    # launcher and workers can validate events.
    && pip install --no-cache-dir -e ${WORKDIR}/common
