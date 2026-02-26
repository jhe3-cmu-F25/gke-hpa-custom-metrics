"""
GCP configuration loader and Dataproc job helper.

All sensitive values (project ID, region, cluster name) are read from
environment variables so they never need to be hard-coded or committed.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config values loaded from .env
# ---------------------------------------------------------------------------

GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
GCP_REGION: str = os.getenv("GCP_REGION", "us-central1")
DATAPROC_CLUSTER_NAME: str = os.getenv("DATAPROC_CLUSTER_NAME", "")

# Path to the JAR / main class that will be submitted as a Hadoop job
DATAPROC_JAR_URI: str = os.getenv("DATAPROC_JAR_URI", "")
DATAPROC_MAIN_CLASS: str = os.getenv("DATAPROC_MAIN_CLASS", "")


def _validate_config() -> None:
    """Raise a clear error if required GCP config is missing."""
    missing = [
        name
        for name, value in [
            ("GCP_PROJECT_ID", GCP_PROJECT_ID),
            ("DATAPROC_CLUSTER_NAME", DATAPROC_CLUSTER_NAME),
        ]
        if not value
    ]
    if missing:
        raise EnvironmentError(
            f"Missing required GCP environment variables: {', '.join(missing)}"
        )


def trigger_dataproc_job(job_args: list[str] | None = None) -> str:
    """
    Submit a Hadoop job to Dataproc using the Google Cloud Python SDK.

    This is a *placeholder* implementation.  When the Dataproc cluster is
    provisioned and the JAR is uploaded to GCS, replace the body of this
    function with the real submission logic shown in the comments below.

    Parameters
    ----------
    job_args:
        Optional list of CLI arguments to pass to the Hadoop job,
        e.g. ``["gs://my-bucket/input", "gs://my-bucket/output"]``.

    Returns
    -------
    str
        The Dataproc job ID (or a placeholder string while not yet implemented).
    """
    _validate_config()

    logger.info(
        "trigger_dataproc_job called — project=%s, region=%s, cluster=%s, args=%s",
        GCP_PROJECT_ID,
        GCP_REGION,
        DATAPROC_CLUSTER_NAME,
        job_args,
    )

    # ------------------------------------------------------------------
    # TODO: Replace the placeholder below with real Dataproc submission.
    #
    # Example using google-cloud-dataproc:
    #
    #   from google.cloud import dataproc_v1
    #
    #   job_client = dataproc_v1.JobControllerClient(
    #       client_options={"api_endpoint": f"{GCP_REGION}-dataproc.googleapis.com:443"}
    #   )
    #
    #   job = {
    #       "placement": {"cluster_name": DATAPROC_CLUSTER_NAME},
    #       "hadoop_job": {
    #           "main_jar_file_uri": DATAPROC_JAR_URI,
    #           "main_class": DATAPROC_MAIN_CLASS,
    #           "args": job_args or [],
    #       },
    #   }
    #
    #   operation = job_client.submit_job_as_operation(
    #       request={"project_id": GCP_PROJECT_ID, "region": GCP_REGION, "job": job}
    #   )
    #   response = operation.result()
    #   job_id = response.reference.job_id
    #   logger.info("Dataproc job submitted: %s", job_id)
    #   return job_id
    # ------------------------------------------------------------------

    placeholder_job_id = "dataproc-job-not-yet-implemented"
    logger.warning("Dataproc submission is a placeholder — returning %s", placeholder_job_id)
    return placeholder_job_id
