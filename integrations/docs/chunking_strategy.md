# Chunking Strategy

## Overview

This document describes the text chunking strategy used in the RAG (Retrieval-Augmented Generation) knowledge base ingestion pipeline. The chunking strategy is designed to split documents into optimally-sized chunks while preserving semantic meaning and document structure.

## Configuration

### Chunking Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `CHUNK_SIZE` | 1000 | Maximum characters per chunk |
| `CHUNK_OVERLAP` | 200 | Character overlap between consecutive chunks |

### Markdown Header Splitting

For markdown files, the system splits on the following header levels:

```python
headers_to_split_on = [
    ("#", "header_1"),
    ("##", "header_2"),
    ("###", "header_3"),
    ("####", "header_4"),
]
```

> **Note**: Header names use underscores (e.g., `header_1`) to comply with Weaviate's GraphQL naming requirements (`/[_A-Za-z][_0-9A-Za-z]*/`).

## Supported File Formats

| Format | Extensions | Splitting Strategy |
|--------|------------|-------------------|
| Markdown | `.md` | MarkdownHeaderTextSplitter (primary) |
| PDF | `.pdf` | PyPDF2 extraction + RecursiveCharacterTextSplitter |
| Text | `.txt`, `.rst`, `.text` | RecursiveCharacterTextSplitter |

## Chunking Algorithm

The chunking strategy uses a **two-tier approach** to ensure optimal chunk sizes while preserving document structure.

### Tier 1: Primary Splitting

#### Markdown Files

1. Uses `MarkdownHeaderTextSplitter` from LangChain
2. Splits content based on header hierarchy (H1-H4)
3. Preserves document structure and semantic meaning
4. Maintains header metadata in chunk objects

#### Other Files (PDF, TXT, RST)

1. Extracts text content from file
2. Applies `RecursiveCharacterTextSplitter` directly

### Tier 2: Secondary Splitting

After primary splitting, chunks are checked for size compliance:

1. If a chunk exceeds `CHUNK_SIZE` (1000 characters), it is further split
2. Secondary splitting uses `RecursiveCharacterTextSplitter` with:
   - `chunk_size=1000`
   - `chunk_overlap=200`
3. Ensures all final chunks fit within size constraints

### Fallback Mechanism

If markdown splitting fails (malformed markdown), the system automatically falls back to `RecursiveCharacterTextSplitter` with a warning log.

## Processing Flow

```
1. Read document text
2. Determine file type by extension
3. Apply primary splitting strategy
4. Check chunk sizes
5. Apply secondary splitting if needed
6. Extract text content and metadata
7. Generate chunk DataFrame
```

## Chunk Schema

Each chunk is stored in Weaviate with the following properties:

### Core Content
| Property | Type | Description |
|----------|------|-------------|
| `text` | text | Text content of the chunk |
| `title` | text | Title of the document/section/heading |

### Document Reference
| Property | Type | Description |
|----------|------|-------------|
| `document_id` | text | Stable ID referencing source document |
| `chunk_id` | int | Sequential ID for reordering chunks |
| `section` | text | Section or subheading of extraction |
| `source_filename` | text | Original filename |

### Source Information
| Property | Type | Description |
|----------|------|-------------|
| `folder_path` | text | Folder path where document was located |
| `source_type` | text | Source file type (pdf, md, docx, txt, etc.) |

### Metadata & Tracking
| Property | Type | Description |
|----------|------|-------------|
| `last_modified` | date | Last modified timestamp of original file |
| `indexed_at` | date | Timestamp when chunk was indexed |
| `hash` | text | Hash of chunk text for change detection |
| `tags` | text[] | List of topic tags or custom metadata |
| `category` | text | High-level document classification |
| `pipeline_version` | text | Version of ingestion pipeline |

### Vectorization
- **Vectorizer**: `text2vec-openai`
- **Model**: `ada`
- **Model Version**: `002`

## Data Structures

### Input DataFrame

```python
{
    "folder_path": str,        # Source folder path
    "title": str,              # Filename without extension
    "text": str,               # Document text content
    "file_extension": str      # File type (.md, .pdf, .txt, etc.)
}
```

### Output DataFrame

```python
{
    "folder_path": str,        # Preserved from input
    "title": str,              # Preserved from input
    "text": str,               # Chunk text content
    "file_extension": str,     # Preserved from input
    "chunk_metadata": dict     # Metadata from splitting (headers, etc.)
}
```

## Dependencies

The chunking strategy relies on the following LangChain packages:

```
langchain>=0.3.0
langchain-core>=0.3.0
langchain-community>=0.3.0
langchain-text-splitters>=0.3.0
```

### Key Classes

- `langchain_text_splitters.RecursiveCharacterTextSplitter`
- `langchain_text_splitters.MarkdownHeaderTextSplitter`
- `langchain_core.documents.Document`

## Airflow Task Integration

The chunking logic is implemented in the `chunk_text` task within the RAG ingestion DAG:

- **Task ID**: `chunk_text`
- **File**: [weaviate_rag_kb_ingest.py](../dags/weaviate/weaviate_rag_kb_ingest.py#L305-L425)
- **Execution**: Dynamically mapped task running in parallel for each document

### Logging

The task logs the following metrics:

```python
t_log.info(f"Total chunks created: {len(df)}")
t_log.info(f"Average chunk size: {df['text'].str.len().mean():.0f} characters")
```

## Configuration Files

### Schema Definition

The complete Weaviate schema is defined in:
- [include/schema.json](../include/schema.json)

### Environment Variables

| Variable | Description |
|----------|-------------|
| `INGESTION_FOLDERS_LOCAL_PATHS` | Paths to folders containing documents |
| `WEAVIATE_CONN_ID` | Airflow connection ID for Weaviate |
| `WEAVIATE_CLASS_NAME` | Target Weaviate class name |
| `WEAVIATE_VECTORIZER` | Vectorizer to use |
| `WEAVIATE_SCHEMA_PATH` | Path to schema.json file |

