# :smile: Ask Junior
A **Retrieval-Augmented Generation (RAG)** knowledge base assistant using **Weaviate** and **OpenAI** to answer user questions from a custom document collection. The answers are retrieved from ingested markdown files, chunked, stored in a vector database, and served through a Streamlit app.

## Features
- Ingest markdown files into **Weaviate**.
- Chunk large documents automatically.
- Vectorize and store text using **text2vec-openai**.
- Retrieve the most relevant chunks based on user queries.
- Generate natural language answers using **OpenAI GPT-4**.
- Streamlit interface for easy question-answering.

## Project Structure
```bash
├── include/
│   ├── data/                  # Markdown files to ingest
│   └── schema.json             # Weaviate schema definition
├── dags/
│   └── rag_dag.py              # Airflow DAG for ingestion
├── include/
│   └── app.py                  # Streamlit application
├── requirements.txt            # Python dependencies
└── README.md
```

## Requirements
- Astro CLI

## Environment Variables
Set the following environment variables:
```bash
INGESTION_FOLDERS_LOCAL_PATHS="include/data/"
WEAVIATE_CONN_ID="weaviate_default"
WEAVIATE_CLASS_NAME="MYDATA"
WEAVIATE_VECTORIZER="text2vec-openai"
WEAVIATE_SCHEMA_PATH="include/schema.json"

OPENAI_API_KEY="<YOUR-OPENAI-API-KEY>"

AIRFLOW_CONN_WEAVIATE_DEFAULT='{
    "conn_type": "weaviate",
    "host": "http://weaviate:8081/",
    "extra": {
        "token":"adminkey",
        "additional_headers" : {"X-Openai-Api-Key": "<YOUR-OPENAI-API-KEY>"}
    }
}'
```

## Installation
1. Clone the repository:
```bash
git clone https://github.com/lorenzouriel/ask-junior.git
cd ask-junior
```

2. Tun the applications:
```bash
astro dev start
```

## Usage Example
1. Add markdown guides to `include/data/`.
2. Trigger the Airflow DAG to ingest and vectorize documents.
3. Open the Streamlit app.
4. Ask a question like: `What is the company?`
5. View the generated answer and source chunks.