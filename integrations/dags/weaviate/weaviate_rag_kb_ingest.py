"""
## Overview
This DAG ingests text data from various document formats, intelligently chunks the text based on document type, and ingests the chunks into a Weaviate vector database for Retrieval-Augmented Generation (RAG) applications.

## DAG Information
- **DAG ID**: `weaviate_rag_kb_ingest`
- **Schedule**: `@daily` (runs once per day at midnight)
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

### 3. Fetch Ingestion Folders
- **Task ID**: `fetch_ingestion_folders_local_paths`
- **Purpose**: Lists all folders in the ingestion directory
- **Returns**: List of folder paths to process

### 4. Extract Document Text (Dynamic)
- **Task ID**: `extract_document_text`
- **Type**: Dynamically mapped task (runs in parallel for each folder)
- **Purpose**: Extracts text from various document formats
- **Supported Formats**: `.md`, `.pdf`, `.txt`, `.rst`, `.text`
- **Output**: DataFrame with columns:
  - `folder_path`: Source folder path
  - `title`: Document title (filename without extension)
  - `text`: Extracted document text
  - `file_extension`: File type for smart chunking

### 5. Chunk Text (Dynamic)
- **Task ID**: `chunk_text`
- **Type**: Dynamically mapped task (runs in parallel for each DataFrame)
- **Purpose**: Splits documents into smaller chunks for better retrieval
- **Chunking Strategy**:
  - **Markdown files**: MarkdownHeaderTextSplitter (structure-aware, preserves headers)
  - **Other files**: RecursiveCharacterTextSplitter (general text chunking)
  - **Secondary splitting**: Large chunks are further split to ensure optimal size
- **Chunk Settings**:
  - Chunk size: 1000 characters
  - Overlap: 200 characters
- **Output**: DataFrame with chunked text and metadata

### 6. Ingest Data (Dynamic)
- **Task ID**: `ingest_data`
- **Type**: Dynamically mapped task (runs in parallel for each chunk set)
- **Purpose**: Ingests chunks into Weaviate vector database
- **Operator**: `WeaviateIngestOperator`
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

_CREATE_CLASS_TASK_ID = "create_class"
_CLASS_ALREADY_EXISTS_TASK_ID = "class_already_exists"

@dag(
    dag_display_name="weaviate_rag_kb_ingest",
    description="Ingest knowledge into the vector database for RAG.",
    start_date=datetime(2025, 11, 11),
    schedule="@daily",
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
    # Import heavy dependencies inside the DAG function to speed up DAG parsing
    from airflow.providers.weaviate.operators.weaviate import WeaviateIngestOperator
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
    def fetch_ingestion_folders_local_paths(ingestion_folders_local_path):
        # get all the folders in the given location
        folders = os.listdir(ingestion_folders_local_path)

        # filter out folders to ignore (e.g., .git, .vscode, node_modules, etc.)
        ignore_folders = {'.git', '.vscode', '.idea', 'node_modules', '__pycache__', '.DS_Store'}

        # return the full path of the folders, excluding ignored ones
        return [
            os.path.join(ingestion_folders_local_path, folder)
            for folder in folders
            if folder not in ignore_folders and os.path.isdir(os.path.join(ingestion_folders_local_path, folder))
        ]

    fetch_ingestion_folders_local_paths_obj = fetch_ingestion_folders_local_paths(
        ingestion_folders_local_path=_INGESTION_FOLDERS_LOCAL_PATHS
    )

    @task(
        map_index_template="{{ my_custom_map_index }}",
    )
    def extract_document_text(ingestion_folder_local_path):
        """
        Extract information from various document types in a folder.
        Supports: .md (markdown), .txt, .rst, .pdf

        Args:
            folder_path (str): Path to the folder containing documents.
        Returns:
            pd.DataFrame: DataFrame with columns: folder_path, title, text, file_extension
        """
        import pandas as pd
        from PyPDF2 import PdfReader

        # Supported file extensions for text extraction
        supported_extensions = [".md", ".txt", ".rst", ".text", ".pdf"]

        files = [
            f for f in os.listdir(ingestion_folder_local_path)
            if any(f.endswith(ext) for ext in supported_extensions)
        ]

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
        ingestion_folder_local_path=fetch_ingestion_folders_local_paths_obj
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

    ingest_data = WeaviateIngestOperator.partial(
        task_id="ingest_data",
        conn_id=_WEAVIATE_CONN_ID,
        class_name=_WEAVIATE_CLASS_NAME,
        map_index_template="Ingested files from: {{ task.input_data.to_dict()['folder_path'][0] }}.",
    ).expand(input_data=chunk_text_obj)

    chain(
        [chunk_text_obj, weaviate_ready],
        ingest_data,
    )


rag_dag()
