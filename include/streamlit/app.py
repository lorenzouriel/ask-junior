import streamlit as st
import os
from openai import OpenAI
import weaviate

WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME")


# -------------------------------
# Weaviate Retrieval Functions
# -------------------------------
def get_relevant_chunks(user_prompt, limit=5, certainty=0.75):
    """Retrieve the most relevant chunks from Weaviate based on a user question."""

    client = weaviate.Client(
        url="http://weaviate:8081",
        auth_client_secret=weaviate.AuthApiKey("adminkey"),
        additional_headers={"X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY")},
    )

    response = (
        client.query
        .get(WEAVIATE_CLASS_NAME, ["title", "text", "folder_path"])
        .with_near_text({"concepts": [user_prompt], "certainty": certainty})
        .with_limit(limit)
        .do()
    )

    objects = response.get("data", {}).get("Get", {}).get(WEAVIATE_CLASS_NAME, [])

    # Fallback if no objects match certainty
    if not objects:
        response = (
            client.query
            .get(WEAVIATE_CLASS_NAME, ["title", "text", "folder_path"])
            .with_near_text({"concepts": [user_prompt]})
            .with_limit(limit)
            .do()
        )
        objects = response.get("data", {}).get("Get", {}).get(WEAVIATE_CLASS_NAME, [])

    return objects

def get_answer(chunks, user_prompt):
    """Generate a concise answer to the user's question using the retrieved chunks."""

    context_text = ""
    for chunk in chunks:
        title = chunk.get("title", "unknown")
        text = chunk.get("text", "no text")
        context_text += f"Source: {title}\n{text}\n\n"

    inference_prompt = f"""
        You are an expert assistant answering user questions based on the provided context. 
        Provide a clear, concise answer. If the answer is not in the context, respond: 
        'I could not find a reliable answer in the knowledge base.'

        Context:
        {context_text}

        User question: {user_prompt}
    """

    client = OpenAI()
    chat_completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": inference_prompt}],
    )

    return chat_completion.choices[0].message.content


# -------------------------------
# Streamlit App
# -------------------------------
st.title("Ask Junior")
st.header("Ask a question")

user_prompt = st.text_input("Your question:", "")
limit = st.slider("Retrieve X most relevant chunks:", 1, 20, 5)
certainty = st.slider("Certainty threshold for relevancy", 0.0, 1.0, 0.75)

if st.button("Get Answer") and user_prompt:
    st.header("Answer")
    with st.spinner(text="Searching knowledge base... 🤔"):
        chunks = get_relevant_chunks(user_prompt, limit=limit, certainty=certainty)
        answer = get_answer(chunks, user_prompt)

        st.success("Done! ✅")
        st.write(answer)

        st.header("Sources")
        if chunks:
            for i, chunk in enumerate(chunks):
                st.write(f"Source {i+1}:")
                st.write(f"Title: {chunk.get('title', 'N/A')}")
                st.write(f"Folder: {chunk.get('folder_path', 'N/A')}")
                st.write("---")
        else:
            st.write("No sources found.")
