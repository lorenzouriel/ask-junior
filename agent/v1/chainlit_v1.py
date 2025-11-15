import chainlit as cl
import os
from openai import OpenAI
import weaviate
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME")
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_AUTH = os.getenv("WEAVIATE_AUTH")
OPEN_API_API_KEY = os.getenv("OPENAI_API_KEY")

# Default settings
DEFAULT_LIMIT = 5
DEFAULT_CERTAINTY = 0.75

# -------------------------------
# Weaviate Retrieval Functions
# -------------------------------
def get_relevant_chunks(user_prompt, limit=5, certainty=0.75):
    """Retrieve the most relevant chunks from Weaviate based on a user question."""

    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(WEAVIATE_AUTH),
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
# Chainlit App
# -------------------------------
@cl.on_chat_start
async def start():
    """Initialize the chat session with welcome message and settings."""
    await cl.Message(
        content="Welcome to Ask Junior! Ask me any question about the knowledge base."
    ).send()

    # Initialize user session settings
    cl.user_session.set("limit", DEFAULT_LIMIT)
    cl.user_session.set("certainty", DEFAULT_CERTAINTY)

    # Create settings UI
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Slider(
                id="limit",
                label="Number of chunks to retrieve",
                initial=DEFAULT_LIMIT,
                min=1,
                max=20,
                step=1,
            ),
            cl.input_widget.Slider(
                id="certainty",
                label="Certainty threshold",
                initial=DEFAULT_CERTAINTY,
                min=0.0,
                max=1.0,
                step=0.05,
            ),
        ]
    ).send()

@cl.on_settings_update
async def setup_agent(settings):
    """Update settings when user changes them."""
    cl.user_session.set("limit", settings["limit"])
    cl.user_session.set("certainty", settings["certainty"])

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming user messages."""
    user_prompt = message.content

    # Get settings from user session
    limit = cl.user_session.get("limit")
    certainty = cl.user_session.get("certainty")

    # Create a message to show progress
    msg = cl.Message(content="")
    await msg.send()

    # Retrieve relevant chunks
    msg.content = "Searching knowledge base..."
    await msg.update()

    chunks = get_relevant_chunks(user_prompt, limit=limit, certainty=certainty)

    # Generate answer
    msg.content = "Generating answer..."
    await msg.update()

    answer = get_answer(chunks, user_prompt)

    # Display answer
    msg.content = answer
    await msg.update()

    # Display sources as elements
    if chunks:
        elements = []
        sources_text = "\n\n**Sources:**\n"
        for i, chunk in enumerate(chunks):
            title = chunk.get('title', 'N/A')
            folder = chunk.get('folder_path', 'N/A')
            text = chunk.get('text', '')

            sources_text += f"\n{i+1}. **{title}**\n   - Folder: {folder}\n"

            # Create text elements for each source
            elements.append(
                cl.Text(
                    name=f"source_{i+1}",
                    content=f"**Title:** {title}\n**Folder:** {folder}\n\n**Content:**\n{text}",
                    display="side"
                )
            )

        # Append sources summary to message
        msg.content += sources_text
        await msg.update()

        # Send source elements
        msg.elements = elements
        await msg.update()
    else:
        msg.content += "\n\n**Sources:** No sources found."
        await msg.update()
