"""
## Overview
This DAG ingests text data from various document formats, intelligently chunks the text based on document type,
and ingests the chunks into a Weaviate vector database for Retrieval-Augmented Generation (RAG) applications.

Uses **git-based change detection** to only process new or modified files, avoiding unnecessary reprocessing.

## DAG Information
- **DAG ID**: `weaviate_rag_kb_ingest`
- **Schedule**:  `0 */4 * * *` (every 4 hours)
- **Start Date**: 2025-11-11
- **Owner**: data_team/lorenzo.uriel
- **Tags**: `rag`, `weaviate`

## Supported File Formats
- **Markdown** (`.md`): Structure-aware chunking using MarkdownHeaderTextSplitter
- **PDF** (`.pdf`): Text extraction with PyPDF2
- **Text** (`.txt`, `.rst`, `.text`): Standard text processing

## Task Flow

### 1. Check Weaviate Class
- **Task ID**: `check_class`
- **Type**: Branch task
- **Purpose**: Determines if the target class exists in Weaviate schema
- **Branches**:
  - If class doesn't exist → `create_class`
  - If class exists → `class_already_exists`

### 2. Create Class (Conditional)
- **Task ID**: `create_class`
- **Purpose**: Creates the Weaviate class using schema from JSON file
- **Runs**: Only if class doesn't exist

### 3. Get Changed Files
- **Task ID**: `get_changed_files`
- **Purpose**: Uses git to detect files changed since last successful ingestion
- **Returns**: List of changed file paths (relative to repo root)

### 4. Fetch Ingestion Folders
- **Task ID**: `fetch_ingestion_folders_local_paths`
- **Purpose**: Lists folders that contain changed files
- **Returns**: List of folder paths with changes to process

### 5. Extract Document Text (Dynamic)
- **Task ID**: `extract_document_text`
- **Type**: Dynamically mapped task (runs in parallel for each folder)
- **Purpose**: Extracts text only from changed documents
- **Supported Formats**: `.md`, `.pdf`, `.txt`, `.rst`, `.text`
- **Output**: DataFrame with extracted document data

### 6. Chunk Text (Dynamic)
- **Task ID**: `chunk_text`
- **Type**: Dynamically mapped task (runs in parallel for each DataFrame)
- **Purpose**: Splits documents into smaller chunks for better retrieval
- **Chunking Strategy**:
  - **Markdown files**: MarkdownHeaderTextSplitter (structure-aware, preserves headers)
  - **Other files**: RecursiveCharacterTextSplitter (general text chunking)
- **Chunk Settings**:
  - Chunk size: 1000 characters
  - Overlap: 200 characters

### 7. Delete Old Chunks (Dynamic)
- **Task ID**: `delete_old_chunks`
- **Purpose**: Removes existing chunks for files being re-ingested
- **Runs**: Before ingesting updated content

### 8. Ingest Data (Dynamic)
- **Task ID**: `ingest_data`
- **Type**: Dynamically mapped task (runs in parallel for each chunk set)
- **Purpose**: Ingests chunks into Weaviate vector database

### 9. Update Last Commit
- **Task ID**: `update_last_commit`
- **Purpose**: Stores the current git commit hash for next run's change detection
"""

from airflow.sdk import dag, task
from datetime import datetime, timedelta
import os
import logging

from include.notifier.slack import slack_fail_alert

t_log = logging.getLogger("airflow.task")

# Variables used in the DAG
_INGESTION_FOLDERS_LOCAL_PATHS = os.getenv("INGESTION_FOLDERS_LOCAL_PATHS")

_WEAVIATE_CONN_ID = os.getenv("WEAVIATE_CONN_ID")
_WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME")
_WEAVIATE_VECTORIZER = os.getenv("WEAVIATE_VECTORIZER")
_WEAVIATE_SCHEMA_PATH = os.getenv("WEAVIATE_SCHEMA_PATH")

# Airflow Variable name to store last processed git commit
_LAST_COMMIT_VAR_NAME = "rag_ingest_last_commit"

_CREATE_CLASS_TASK_ID = "create_class"
_CLASS_ALREADY_EXISTS_TASK_ID = "class_already_exists"

@dag(
    dag_display_name="weaviate_rag_kb_ingest",
    description="Ingest knowledge into the vector database for RAG.",
    start_date=datetime(2025, 11, 11),
    schedule='0 */4 * * *',
    catchup=False,
    max_consecutive_failed_dag_runs=5,
    tags=["rag", "weaviate"],
    default_args={
        'owner': 'data_team/lorenzo.uriel',
        'retries': 2,
        'retry_delay': timedelta(minutes=5),
        'on_failure_callback': slack_fail_alert,
    },
    doc_md=__doc__,
)
def rag_dag():
    # Import lightweight dependencies at DAG level
    # Note: Heavy weaviate imports are done inside tasks at runtime to avoid DAG parse timeout
    from airflow.providers.standard.operators.empty import EmptyOperator
    from airflow.models.baseoperator import chain

    @task.branch(retries=4)
    def check_class(
        conn_id: str,
        class_name: str,
        create_class_task_id: str,
        class_already_exists_task_id: str,
    ):
        """
        Check if the target class exists in the Weaviate schema.
        
        Args:
            conn_id: The connection ID to use.
            class_name: The name of the class to check.
            create_class_task_id: The task ID to execute if the class does not exist.
            class_already_exists_task_id: The task ID to execute if the class already exists.
        
        Returns:
            str: Task ID of the next task to execute.
        """
        from airflow.providers.weaviate.hooks.weaviate import WeaviateHook

        # connect to Weaviate using the Airflow connection `conn_id`
        hook = WeaviateHook(conn_id)

        # retrieve the existing schema from the Weaviate instance
        schema = hook.get_schema()
        existing_classes = {cls["class"]: cls for cls in schema.get("classes", [])}

        # if the target class does not exist yet, we will need to create it
        if class_name not in existing_classes:
            t_log.info(f"Class {class_name} does not exist yet.")
            return create_class_task_id
        # if the target class exists it does not need to be created
        else:
            return class_already_exists_task_id

    check_class_obj = check_class(
        conn_id=_WEAVIATE_CONN_ID,
        class_name=_WEAVIATE_CLASS_NAME,
        create_class_task_id=_CREATE_CLASS_TASK_ID,
        class_already_exists_task_id=_CLASS_ALREADY_EXISTS_TASK_ID,
    )

    @task
    def create_class(
        conn_id: str, class_name: str, vectorizer: str, schema_json_path: str
    ) -> None:
        """
        Create a class in the Weaviate schema.
        
        Args:
            conn_id: The connection ID to use.
            class_name: The name of the class to create.
            vectorizer: The vectorizer to use for the class.
            schema_json_path: The path to the schema JSON file (relative or absolute).
        """
        import json
        import os
        from airflow.providers.weaviate.hooks.weaviate import WeaviateHook

        weaviate_hook = WeaviateHook(conn_id)

        # Convert relative path to absolute path based on Airflow home directory
        if not os.path.isabs(schema_json_path):
            schema_json_path = os.path.join("/opt/airflow", schema_json_path)

        with open(schema_json_path) as f:
            schema = json.load(f)
            class_obj = next(
                (item for item in schema["classes"] if item["class"] == class_name),
                None,
            )
            class_obj["vectorizer"] = vectorizer

        weaviate_hook.create_class(class_obj)

    create_class_obj = create_class(
        conn_id=_WEAVIATE_CONN_ID,
        class_name=_WEAVIATE_CLASS_NAME,
        vectorizer=_WEAVIATE_VECTORIZER,
        schema_json_path=_WEAVIATE_SCHEMA_PATH,
    )

    class_already_exists = EmptyOperator(task_id=_CLASS_ALREADY_EXISTS_TASK_ID)

    weaviate_ready = EmptyOperator(task_id="weaviate_ready", trigger_rule="none_failed")

    chain(check_class_obj, [create_class_obj, class_already_exists], weaviate_ready)

    @task
    def get_changed_files(ingestion_folders_local_path: str, last_commit_var_name: str) -> dict:
        """
        Get list of files changed since last successful ingestion using git.

        Args:
            ingestion_folders_local_path: Base path to the ingestion folders
            last_commit_var_name: Airflow Variable name storing last processed commit

        Returns:
            dict with:
                - changed_files: List of changed file paths (relative to ingestion folder)
                - current_commit: Current git commit hash
                - is_initial_run: True if no previous commit (process all files)
        """
        import subprocess
        from airflow.models import Variable

        # Get the last processed commit from Airflow Variable
        last_commit = Variable.get(last_commit_var_name, default_var=None)

        # Get current commit hash
        try:
            current_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=ingestion_folders_local_path,
                text=True
            ).strip()
        except subprocess.CalledProcessError as e:
            t_log.warning(f"Failed to get current git commit: {e}. Will process all files.")
            return {
                "changed_files": None,  # None means process all files
                "current_commit": None,
                "is_initial_run": True
            }

        # If no previous commit, this is initial run - process all files
        if not last_commit:
            t_log.info(f"Initial run - no previous commit found. Will process all files.")
            return {
                "changed_files": None,
                "current_commit": current_commit,
                "is_initial_run": True
            }

        # Get changed files since last commit
        try:
            # Get files that were added, modified, or renamed
            diff_output = subprocess.check_output(
                ["git", "diff", "--name-only", "--diff-filter=AMR", last_commit, "HEAD"],
                cwd=ingestion_folders_local_path,
                text=True
            ).strip()

            if diff_output:
                changed_files = diff_output.split('\n')
                # Filter to only supported file types
                supported_extensions = {".md", ".txt", ".rst", ".text", ".pdf"}
                changed_files = [
                    f for f in changed_files
                    if os.path.splitext(f)[1].lower() in supported_extensions
                ]
            else:
                changed_files = []

            t_log.info(f"Found {len(changed_files)} changed files since commit {last_commit[:8]}")
            t_log.info(f"Changed files: {changed_files}")

            return {
                "changed_files": changed_files,
                "current_commit": current_commit,
                "is_initial_run": False
            }

        except subprocess.CalledProcessError as e:
            t_log.warning(f"Failed to get git diff: {e}. Will process all files.")
            return {
                "changed_files": None,
                "current_commit": current_commit,
                "is_initial_run": True
            }

    get_changed_files_obj = get_changed_files(
        ingestion_folders_local_path=_INGESTION_FOLDERS_LOCAL_PATHS,
        last_commit_var_name=_LAST_COMMIT_VAR_NAME
    )

    @task
    def fetch_ingestion_folders_local_paths(ingestion_folders_local_path, changed_files_info: dict):
        """
        Get folders that contain changed files.

        Args:
            ingestion_folders_local_path: Base path to ingestion folders
            changed_files_info: Dict from get_changed_files task

        Returns:
            List of dicts with folder_path and changed_files for each folder
        """
        folders = os.listdir(ingestion_folders_local_path)

        # filter out folders to ignore (.git, .vscode, node_modules, etc.)
        ignore_folders = {'.git', '.vscode', '.idea', 'node_modules', '__pycache__', '.DS_Store'}

        # Get all valid folders
        all_folders = [
            folder for folder in folders
            if folder not in ignore_folders and os.path.isdir(os.path.join(ingestion_folders_local_path, folder))
        ]

        changed_files = changed_files_info.get("changed_files")
        is_initial_run = changed_files_info.get("is_initial_run", False)

        # If initial run or no changed files info, return all folders
        if is_initial_run or changed_files is None:
            t_log.info(f"Initial run - processing all {len(all_folders)} folders")
            return [
                {
                    "folder_path": os.path.join(ingestion_folders_local_path, folder),
                    "changed_files": None  # None means process all files in folder
                }
                for folder in all_folders
            ]

        # If no files changed, return empty list
        if not changed_files:
            t_log.info("No files changed - nothing to process")
            return []

        # Group changed files by folder
        folders_with_changes = {}
        for file_path in changed_files:
            # Get the first directory component (folder name)
            parts = file_path.split('/')
            if len(parts) >= 2:
                folder_name = parts[0]
                file_name = '/'.join(parts[1:])  # Rest of the path
            else:
                # File is in root, use root folder
                folder_name = ""
                file_name = file_path

            if folder_name in all_folders:
                if folder_name not in folders_with_changes:
                    folders_with_changes[folder_name] = []
                folders_with_changes[folder_name].append(file_name)

        t_log.info(f"Found changes in {len(folders_with_changes)} folders: {list(folders_with_changes.keys())}")

        # Return folders with their changed files
        return [
            {
                "folder_path": os.path.join(ingestion_folders_local_path, folder),
                "changed_files": files
            }
            for folder, files in folders_with_changes.items()
        ]

    fetch_ingestion_folders_local_paths_obj = fetch_ingestion_folders_local_paths(
        ingestion_folders_local_path=_INGESTION_FOLDERS_LOCAL_PATHS,
        changed_files_info=get_changed_files_obj
    )

    @task(
        map_index_template="{{ my_custom_map_index }}",
    )
    def extract_document_text(folder_info: dict):
        """
        Extract information from changed document types in a folder.
        Supports: .md (markdown), .txt, .rst, .pdf

        Args:
            folder_info: Dict with folder_path and changed_files (list or None for all)
        
        Returns:
            pd.DataFrame: DataFrame with columns: folder_path, title, text, file_extension
        """
        import pandas as pd
        from PyPDF2 import PdfReader

        ingestion_folder_local_path = folder_info["folder_path"]
        changed_files = folder_info.get("changed_files")

        # Supported file extensions for text extraction
        supported_extensions = [".md", ".txt", ".rst", ".text", ".pdf"]

        # Get all supported files in folder
        all_files = [
            f for f in os.listdir(ingestion_folder_local_path)
            if any(f.endswith(ext) for ext in supported_extensions)
        ]

        # Filter to only changed files if specified
        if changed_files is not None:
            # Extract just the filename from changed_files paths
            changed_filenames = {os.path.basename(f) for f in changed_files}
            files = [f for f in all_files if f in changed_filenames]
            t_log.info(f"Processing {len(files)} changed files out of {len(all_files)} total")
        else:
            files = all_files
            t_log.info(f"Processing all {len(files)} files (initial run)")

        titles = []
        texts = []
        file_extensions = []

        for file in files:
            file_path = os.path.join(ingestion_folder_local_path, file)

            # Extract title (filename without extension)
            title = os.path.splitext(file)[0]
            file_ext = os.path.splitext(file)[1].lower()

            titles.append(title)
            file_extensions.append(file_ext)

            # Read file content based on extension
            if file_ext == ".pdf":
                # Extract text from PDF
                try:
                    pdf_reader = PdfReader(file_path)
                    text_content = ""
                    for page in pdf_reader.pages:
                        text_content += page.extract_text() + "\n"
                    texts.append(text_content.strip())
                except Exception as e:
                    t_log.error(f"Error reading PDF {file}: {e}")
                    texts.append("")
            else:
                # Read text-based files
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        texts.append(f.read())
                except Exception as e:
                    t_log.error(f"Error reading file {file}: {e}")
                    texts.append("")

        document_df = pd.DataFrame(
            {
                "folder_path": ingestion_folder_local_path,
                "title": titles,
                "text": texts,
                "file_extension": file_extensions,
                "source_filename": files,  # Original filename with extension
                "source_type": [ext.lstrip('.') for ext in file_extensions],  # File type without dot
            }
        )

        # Remove empty documents
        document_df = document_df[document_df["text"].str.strip() != ""]
        document_df.reset_index(drop=True, inplace=True)

        t_log.info(f"Number of records: {document_df.shape[0]}")
        t_log.info(f"File types: {document_df['file_extension'].value_counts().to_dict()}")

        # get the current context and define the custom map index variable
        from airflow.sdk import get_current_context

        context = get_current_context()
        context["my_custom_map_index"] = (
            f"Extracted files from: {ingestion_folder_local_path}."
        )

        return document_df

    extract_document_text_obj = extract_document_text.expand(
        folder_info=fetch_ingestion_folders_local_paths_obj
    )

    @task(map_index_template="{{ my_custom_map_index }}")
    def chunk_text(df):
        """
        Chunk the text in the DataFrame using appropriate splitter based on file type.
        - Markdown files (.md): Uses MarkdownHeaderTextSplitter for structure-aware chunking
        - Other files: Uses RecursiveCharacterTextSplitter for general text chunking

        Args:
            df (pd.DataFrame): The DataFrame containing the text to chunk.
        
        Returns:
            pd.DataFrame: The DataFrame with the text chunked.
        """
        import pandas as pd
        from langchain_text_splitters import (
            RecursiveCharacterTextSplitter,
            MarkdownHeaderTextSplitter
        )
        from langchain_core.documents import Document

        def chunk_single_document(row):
            """
            Chunk a single document based on its file type.
            - Markdown files (.md): Uses MarkdownHeaderTextSplitter for structure-aware chunking
            - Other files: Uses RecursiveCharacterTextSplitter for general text chunking

            Args:
                row: DataFrame row containing 'title', 'text', and 'file_extension' columns
            Returns:
                list: List of Document objects representing chunks
            """
            text = row['text']
            title = row['title']
            file_extension = row.get('file_extension', '.md')

            # Define chunk size and overlap settings
            CHUNK_SIZE = 1000
            CHUNK_OVERLAP = 200

            # Check if this is a markdown file
            if file_extension == '.md':
                # Use MarkdownHeaderTextSplitter for markdown documents
                # Use GraphQL-compliant names (must match /[_A-Za-z][_0-9A-Za-z]*/)
                headers_to_split_on = [
                    ("#", "header_1"),
                    ("##", "header_2"),
                    ("###", "header_3"),
                    ("####", "header_4"),
                ]

                markdown_splitter = MarkdownHeaderTextSplitter(
                    headers_to_split_on=headers_to_split_on,
                    strip_headers=False
                )

                try:
                    # Split by headers first
                    md_header_splits = markdown_splitter.split_text(text)

                    # If the chunks are still too large, further split them
                    recursive_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=CHUNK_SIZE,
                        chunk_overlap=CHUNK_OVERLAP,
                        length_function=len,
                        is_separator_regex=False,
                    )

                    # Apply secondary splitting if needed
                    final_chunks = []
                    for doc in md_header_splits:
                        # If chunk is larger than threshold, split it further
                        if len(doc.page_content) > CHUNK_SIZE:
                            sub_chunks = recursive_splitter.split_documents([doc])
                            final_chunks.extend(sub_chunks)
                        else:
                            final_chunks.append(doc)

                    return final_chunks if final_chunks else [Document(page_content=text)]

                except Exception as e:
                    t_log.warning(f"Markdown splitting failed for '{title}': {e}. Falling back to recursive splitter.")
                    # Fall through to recursive splitter

            # For non-markdown files or if markdown splitting failed, use RecursiveCharacterTextSplitter
            recursive_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                length_function=len,
                is_separator_regex=False,
            )

            chunks = recursive_splitter.split_documents([Document(page_content=text)])
            return chunks if chunks else [Document(page_content=text)]

        # Apply chunking to each row
        df["chunks"] = df.apply(chunk_single_document, axis=1)

        # Explode the chunks into separate rows
        df = df.explode("chunks", ignore_index=True)
        df.dropna(subset=["chunks"], inplace=True)

        # Extract text content and metadata from Document objects
        df["text"] = df["chunks"].apply(lambda x: x.page_content)
        df["chunk_metadata"] = df["chunks"].apply(lambda x: x.metadata)

        # Extract section headers from chunk metadata (for markdown documents)
        def extract_section(metadata):
            """Extract section info from markdown headers metadata."""
            if not metadata:
                return ""
            # Prioritize lower-level headers for more specific context
            for header_key in ["header_4", "header_3", "header_2", "header_1"]:
                if header_key in metadata:
                    return metadata[header_key]
            return ""

        df["section"] = df["chunk_metadata"].apply(extract_section)

        # Create better title by combining filename with section when available
        def create_enhanced_title(row):
            """Create a more descriptive title combining filename and section."""
            base_title = row["title"]
            section = row.get("section", "")
            if section and section != base_title:
                return f"{base_title} - {section}"
            return base_title

        df["title"] = df.apply(create_enhanced_title, axis=1)

        # Drop the chunks column as we've extracted what we need
        df.drop(["chunks", "chunk_metadata"], inplace=True, axis=1)
        df.reset_index(inplace=True, drop=True)

        # Log chunking statistics
        t_log.info(f"Total chunks created: {len(df)}")
        t_log.info(f"Average chunk size: {df['text'].str.len().mean():.0f} characters")

        # get the current context and define the custom map index variable
        from airflow.sdk import get_current_context

        context = get_current_context()

        context["my_custom_map_index"] = (
            f"Chunked files from a df of length: {len(df)}."
        )

        return df

    chunk_text_obj = chunk_text.expand(df=extract_document_text_obj)

    @task(map_index_template="{{ my_custom_map_index }}")
    def delete_old_chunks(df, conn_id: str, class_name: str):
        """
        Delete existing chunks for files that are being re-ingested.
        This ensures we don't have duplicate or stale chunks.

        Args:
            df: DataFrame with chunks to ingest
            conn_id: Weaviate connection ID
            class_name: Weaviate class name

        Returns:
            The same DataFrame (pass-through for chaining)
        """
        from airflow.providers.weaviate.hooks.weaviate import WeaviateHook
        from airflow.sdk import get_current_context

        if df.empty:
            context = get_current_context()
            context["my_custom_map_index"] = "Empty DataFrame - nothing to delete"
            return df

        hook = WeaviateHook(conn_id)
        client = hook.get_client()

        # Get unique source files from the DataFrame
        source_files = df['source_filename'].unique().tolist()
        folder_path = df['folder_path'].iloc[0] if not df.empty else "unknown"

        deleted_count = 0
        for source_file in source_files:
            try:
                # Delete all existing chunks for this source file
                result = client.batch.delete_objects(
                    class_name=class_name,
                    where={
                        "path": ["source_filename"],
                        "operator": "Equal",
                        "valueText": source_file
                    }
                )
                if result and hasattr(result, 'successful'):
                    deleted_count += result.successful
                t_log.info(f"Deleted old chunks for: {source_file}")
            except Exception as e:
                t_log.warning(f"Error deleting old chunks for {source_file}: {e}")

        t_log.info(f"Deleted {deleted_count} old chunks for {len(source_files)} files")

        context = get_current_context()
        context["my_custom_map_index"] = (
            f"Deleted old chunks from {folder_path}: {deleted_count} chunks for {len(source_files)} files"
        )

        return df

    delete_old_chunks_obj = delete_old_chunks.partial(
        conn_id=_WEAVIATE_CONN_ID,
        class_name=_WEAVIATE_CLASS_NAME,
    ).expand(df=chunk_text_obj)

    @task(map_index_template="{{ my_custom_map_index }}")
    def ingest_data(df, conn_id: str, class_name: str):
        """
        Ingest data into Weaviate using the WeaviateHook directly.
        This avoids importing the heavy WeaviateIngestOperator at DAG parse time.

        Args:
            df: DataFrame with chunks to ingest
            conn_id: Weaviate connection ID
            class_name: Weaviate class name
        """
        from airflow.providers.weaviate.hooks.weaviate import WeaviateHook
        from airflow.sdk import get_current_context

        if df.empty:
            context = get_current_context()
            context["my_custom_map_index"] = "Empty DataFrame - nothing to ingest"
            return

        hook = WeaviateHook(conn_id)
        client = hook.get_client()

        folder_path = df['folder_path'].iloc[0] if not df.empty else "unknown"

        # Convert DataFrame to list of dicts for batch ingestion
        records = df.to_dict(orient='records')

        # Use batch import for efficiency
        with client.batch as batch:
            for record in records:
                # Prepare the data object
                data_object = {
                    "title": record.get("title", ""),
                    "text": record.get("text", ""),
                    "folder_path": record.get("folder_path", ""),
                    "source_filename": record.get("source_filename", ""),
                    "source_type": record.get("source_type", ""),
                    "section": record.get("section", ""),
                }

                batch.add_data_object(
                    data_object=data_object,
                    class_name=class_name
                )

        t_log.info(f"Successfully ingested {len(records)} records into {class_name}")

        context = get_current_context()
        context["my_custom_map_index"] = (
            f"Ingested {len(records)} chunks from {folder_path}"
        )

    ingest_data_obj = ingest_data.partial(
        conn_id=_WEAVIATE_CONN_ID,
        class_name=_WEAVIATE_CLASS_NAME,
    ).expand(df=delete_old_chunks_obj)

    @task
    def update_last_commit(changed_files_info: dict, last_commit_var_name: str):
        """
        Update the Airflow Variable with the current git commit hash.
        This marks this commit as processed for the next run.

        Args:
            changed_files_info: Dict from get_changed_files task
            last_commit_var_name: Airflow Variable name to update
        """
        from airflow.models import Variable

        current_commit = changed_files_info.get("current_commit")
        if current_commit:
            Variable.set(last_commit_var_name, current_commit)
            t_log.info(f"Updated last processed commit to: {current_commit}")
        else:
            t_log.warning("No commit hash available to save")

    update_last_commit_obj = update_last_commit(
        changed_files_info=get_changed_files_obj,
        last_commit_var_name=_LAST_COMMIT_VAR_NAME
    )

    # Define task dependencies
    chain(
        weaviate_ready,
        get_changed_files_obj,
        fetch_ingestion_folders_local_paths_obj,
        extract_document_text_obj,
        chunk_text_obj,
        delete_old_chunks_obj,
        ingest_data_obj,
        update_last_commit_obj,
    )


rag_dag()
