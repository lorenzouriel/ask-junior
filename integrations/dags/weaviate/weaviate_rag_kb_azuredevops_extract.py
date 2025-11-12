"""
This DAG synchronizes a knowledge base repository from Azure DevOps to the local Airflow environment. It intelligently clones the repository on first run and pulls the latest changes on subsequent runs, ensuring the knowledge base is always up-to-date for the ingestion DAG.

## DAG Information
- **DAG ID**: `weaviate_rag_kb_azuredevops_extract`
- **Schedule**: `0 */3 * * *` (every 3 hours)
- **Start Date**: 2025-11-11
- **Owner**: data_team/lorenzo.uriel
- **Tags**: `azure-devops`, `git`, `rag`

## Task Flow
### 1. Check Repository Exists
- **Task ID**: `check_repo_exists`
- **Purpose**: Determines if a valid Git repository exists at the target location
- **Checks**:
  - Existence of `.git` directory
  - Validity of Git repository structure
- **Recovery**: Automatically removes corrupted repositories
- **Returns**: `True` if valid repo exists, `False` otherwise

### 2. Clone Repository
- **Task ID**: `clone_repository`
- **Purpose**: Clones the Azure DevOps repository to local filesystem
- **Runs**: Only if repository doesn't exist
- **Authentication**: Uses PAT token embedded in clone URL
- **Output**: Cloned repository at `/usr/local/airflow/include/knowledge_base`

### 3. Pull Repository
- **Task ID**: `pull_repository`
- **Purpose**: Pulls latest changes from Azure DevOps
- **Runs**: Only if repository already exists
- **Branch**: Pulls from `main` branch
- **Authentication**: Updates remote URL with PAT before pulling

### 4. Verify Sync
- **Task ID**: `verify_sync`
- **Purpose**: Confirms repository exists and displays latest commit
- **Output**: Latest commit information from Git log
- **Always Runs**: After both clone and pull tasks complete
"""

import os
import logging
import subprocess
import shutil
from datetime import datetime, timedelta
from airflow.sdk import dag, task

from include.notifier.slack import slack_fail_alert

# Configuration from environment variables
AZURE_DEVOPS_PAT = os.getenv("AZURE_DEVOPS_PAT")
AZURE_DEVOPS_REPO_URL = os.getenv("AZURE_DEVOPS_REPO_URL")

# Target directory for the repository
REPO_BASE_DIR = "/usr/local/airflow/include"
REPO_NAME = "knowledge_base"
REPO_PATH = os.path.join(REPO_BASE_DIR, REPO_NAME)

# Build authenticated URL
if AZURE_DEVOPS_PAT and AZURE_DEVOPS_REPO_URL:
    # Remove any existing username from URL first
    clean_url = AZURE_DEVOPS_REPO_URL.replace("https://", "")
    # Remove username if present (format: username@domain)
    if "@" in clean_url:
        clean_url = clean_url.split("@", 1)[1]
    # Build authenticated URL with PAT
    auth_url = f"https://{AZURE_DEVOPS_PAT}@{clean_url}"
else:
    auth_url = None
    logging.warning("Azure DevOps credentials not found in environment variables")


@dag(
    dag_id='weaviate_rag_kb_azuredevops_extract',
    description='Clone or Pull Azure DevOps Knowledge Base Repository',
    schedule='0 */3 * * *',
    start_date=datetime(2025, 11, 11),
    catchup=False,
    tags=['azure-devops', 'git', 'rag'],
    default_args={
        'owner': 'data_team/lorenzo.uriel',
        'retries': 2,
        'retry_delay': timedelta(minutes=5),
        'on_failure_callback': slack_fail_alert,
    },
    doc_md=__doc__,
)
def azure_devops_sync():
    """
    DAG to synchronize Azure DevOps repository.
    Clones the repository if it doesn't exist, otherwise pulls latest changes.
    """

    @task
    def check_repo_exists():
        """
        Check if the repository already exists and is valid.

        Returns:
            bool: True if valid repo exists, False otherwise
        """
        git_dir = os.path.join(REPO_PATH, ".git")

        # Check if .git directory exists
        if not os.path.exists(git_dir):
            logging.info(f"Repository doesn't exist at {REPO_PATH}")
            return False

        # Verify it's a valid git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=REPO_PATH,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logging.warning(f"Invalid/corrupted git repository at {REPO_PATH}. Will remove and re-clone.")
            # Remove corrupted repository
            try:
                shutil.rmtree(REPO_PATH)
                logging.info(f"Removed corrupted repository at {REPO_PATH}")
            except Exception as e:
                logging.error(f"Failed to remove corrupted repository: {e}")
            return False

        logging.info(f"Valid repository exists at {REPO_PATH}")
        return True

    @task
    def clone_repository(repo_exists: bool):
        """
        Clone the Azure DevOps repository if it doesn't exist.

        Args:
            repo_exists: Boolean indicating if repository already exists
        """
        if repo_exists:
            logging.info(f"Repository already exists at {REPO_PATH}. Skipping clone.")
            return "Repository already exists"

        if not auth_url:
            raise ValueError("Azure DevOps credentials not configured")

        # Ensure the target directory doesn't exist before cloning
        if os.path.exists(REPO_PATH):
            logging.warning(f"Directory exists at {REPO_PATH} but is not a valid repo. Removing it.")
            try:
                shutil.rmtree(REPO_PATH)
                logging.info(f"Successfully removed existing directory at {REPO_PATH}")
            except Exception as e:
                logging.error(f"Failed to remove directory: {e}")
                raise Exception(f"Cannot clone: directory exists and cannot be removed: {e}")

        logging.info(f"Cloning repository to {REPO_PATH}")

        # Ensure base directory exists
        os.makedirs(REPO_BASE_DIR, exist_ok=True)

        # Clone the repository
        result = subprocess.run(
            ["git", "clone", auth_url, REPO_PATH],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logging.error(f"Clone failed: {result.stderr}")
            raise Exception(f"Failed to clone repository: {result.stderr}")

        logging.info(f"Successfully cloned repository to {REPO_PATH}")
        return f"Cloned to {REPO_PATH}"

    @task
    def pull_repository(repo_exists: bool):
        """
        Pull the latest changes if the repository already exists.

        Args:
            repo_exists: Boolean indicating if repository already exists
        """
        if not repo_exists:
            logging.info("Repository doesn't exist. Skipping pull.")
            return "Repository doesn't exist"

        logging.info(f"Pulling latest changes for repository at {REPO_PATH}")

        # Configure git to use the PAT for authentication
        if AZURE_DEVOPS_PAT and auth_url:
            # Set the remote URL with PAT
            subprocess.run(
                ["git", "remote", "set-url", "origin", auth_url],
                cwd=REPO_PATH,
                capture_output=True,
                text=True
            )

        # Pull the latest changes
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=REPO_PATH,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logging.error(f"Pull failed: {result.stderr}")
            raise Exception(f"Failed to pull repository: {result.stderr}")

        logging.info(f"Successfully pulled latest changes: {result.stdout}")
        return f"Pulled latest changes: {result.stdout}"

    @task
    def verify_sync():
        """
        Verify that the repository exists and show latest commit.
        """
        if not os.path.exists(REPO_PATH):
            logging.warning(f"Repository not found at {REPO_PATH}")
            return "Repository not found"

        # Get latest commit info
        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=REPO_PATH,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            logging.info(f"Latest commit: {result.stdout.strip()}")
            return f"Sync verified. Latest commit: {result.stdout.strip()}"
        else:
            logging.error(f"Failed to verify sync: {result.stderr}")
            return f"Verification failed: {result.stderr}"

    # Define task flow
    repo_exists = check_repo_exists()
    clone_task = clone_repository(repo_exists)
    pull_task = pull_repository(repo_exists)
    verify_task = verify_sync()

    # Set dependencies
    [clone_task, pull_task] >> verify_task

# Instantiate the DAG
azure_devops_sync()