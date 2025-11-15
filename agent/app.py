import chainlit as cl
import os
import time
from openai import OpenAI
import weaviate
from dotenv import load_dotenv

# Import observability and memory modules
from observability import observability_manager
from memory import MemoryManager

# Load environment variables from .env file
load_dotenv()

WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME")
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_AUTH = os.getenv("WEAVIATE_AUTH")
OPEN_API_API_KEY = os.getenv("OPENAI_API_KEY")

# Default settings
DEFAULT_LIMIT = 5
DEFAULT_CERTAINTY = 0.75

# Initialize observability
observability_manager.initialize(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = observability_manager.logger
tracer = observability_manager.tracer

# Initialize memory manager
memory_manager = MemoryManager(
    db_path=os.getenv("MEMORY_DB_PATH", "agent_memory.db")
)

# -------------------------------
# Weaviate Retrieval Functions
# -------------------------------
@observability_manager.trace_operation("weaviate_retrieval")
def get_relevant_chunks(user_prompt, limit=5, certainty=0.75):
    """Retrieve the most relevant chunks from Weaviate based on a user question."""
    logger.info(
        "Retrieving chunks from Weaviate",
        extra={
            "limit": limit,
            "certainty": certainty,
            "prompt_length": len(user_prompt)
        }
    )

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
        logger.warning(f"No chunks found with certainty {certainty}, retrying without certainty threshold")
        response = (
            client.query
            .get(WEAVIATE_CLASS_NAME, ["title", "text", "folder_path"])
            .with_near_text({"concepts": [user_prompt]})
            .with_limit(limit)
            .do()
        )
        objects = response.get("data", {}).get("Get", {}).get(WEAVIATE_CLASS_NAME, [])

    # Record metrics (convert None to string to avoid type errors)
    observability_manager.chunk_counter.add(
        len(objects),
        {
            "certainty": float(certainty) if certainty is not None else 0.0,
            "limit": int(limit) if limit is not None else 0
        }
    )

    logger.info(f"Retrieved {len(objects)} chunks from Weaviate")
    return objects

@observability_manager.trace_operation("llm_inference")
def get_answer(chunks, user_prompt):
    """Generate a concise answer to the user's question using the retrieved chunks."""
    logger.info("Generating answer with LLM", extra={"num_chunks": len(chunks)})

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

    answer = chat_completion.choices[0].message.content

    # Record token usage if available
    if hasattr(chat_completion, 'usage'):
        usage = chat_completion.usage
        observability_manager.token_counter.add(
            usage.total_tokens,
            {
                "model": "gpt-4",
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens
            }
        )
        logger.info(
            "LLM inference completed",
            extra={
                "total_tokens": usage.total_tokens,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens
            }
        )

    return answer

# -------------------------------
# Chainlit App
# -------------------------------
@cl.on_chat_start
async def start():
    """Initialize the chat session with welcome message and settings."""
    session_id = cl.user_session.get("id")

    logger.info(f"New chat session started: {session_id}")

    # Get user info safely
    user = cl.user_session.get("user")
    user_id = user.get("identifier") if user else None

    # Create session in memory
    memory_manager.create_session(
        session_id=session_id,
        user_id=user_id,
        metadata={"platform": "chainlit"}
    )

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
    session_id = cl.user_session.get("id")

    logger.info(
        f"Settings updated for session {session_id}",
        extra={"settings": settings}
    )

    cl.user_session.set("limit", settings["limit"])
    cl.user_session.set("certainty", settings["certainty"])

@cl.on_message
@observability_manager.trace_async_operation("handle_message")
async def main(message: cl.Message):
    """Handle incoming user messages."""
    session_id = cl.user_session.get("id")
    user_prompt = message.content
    start_time = time.time()

    logger.info(
        f"Received message in session {session_id}",
        extra={"message_length": len(user_prompt)}
    )

    # Save user message to memory
    user_message_id = memory_manager.add_message(
        session_id=session_id,
        role="user",
        content=user_prompt
    )

    # Get settings from user session with defaults
    limit = cl.user_session.get("limit") or DEFAULT_LIMIT
    certainty = cl.user_session.get("certainty") or DEFAULT_CERTAINTY

    # Create a message to show progress
    msg = cl.Message(content="")
    await msg.send()

    try:
        # Retrieve relevant chunks
        msg.content = "Searching knowledge base..."
        await msg.update()

        chunks = get_relevant_chunks(user_prompt, limit=limit, certainty=certainty)

        # Generate answer
        msg.content = "Generating answer..."
        await msg.update()

        answer = get_answer(chunks, user_prompt)

        # Calculate duration
        duration = time.time() - start_time

        # Save assistant message to memory
        assistant_message_id = memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            metadata={"chunks_count": len(chunks)}
        )

        # Save interaction to memory
        sources_data = [
            {
                "title": chunk.get("title", "N/A"),
                "folder_path": chunk.get("folder_path", "N/A"),
                "text": chunk.get("text", "")[:500]  # Store first 500 chars
            }
            for chunk in chunks
        ]

        memory_manager.add_interaction(
            session_id=session_id,
            query=user_prompt,
            answer=answer,
            chunks_retrieved=len(chunks),
            certainty_threshold=certainty,
            limit_used=limit,
            sources=sources_data,
            duration_seconds=duration,
            message_id=assistant_message_id
        )

        # Record metrics
        memory_manager.record_metric(
            metric_name="interaction_duration",
            metric_value=duration,
            session_id=session_id
        )

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

        logger.info(
            f"Successfully handled message in {duration:.2f}s",
            extra={
                "session_id": session_id,
                "chunks_retrieved": len(chunks),
                "duration_seconds": duration
            }
        )

        # Force flush telemetry data to ensure it's sent to collector
        observability_manager.force_flush()

    except Exception as e:
        logger.error(
            f"Error handling message: {str(e)}",
            exc_info=True,
            extra={"session_id": session_id}
        )

        # Record error metric
        observability_manager.error_counter.add(
            1,
            {"error_type": type(e).__name__}
        )

        msg.content = f"An error occurred while processing your request: {str(e)}"
        await msg.update()


@cl.on_chat_end
async def end():
    """Handle chat session end."""
    session_id = cl.user_session.get("id")

    logger.info(f"Chat session ended: {session_id}")

    # Get session metrics and log them
    metrics = memory_manager.get_session_metrics(session_id)

    # Convert metrics to individual log entries (OpenTelemetry attributes must be primitive types)
    logger.info(
        f"Session {session_id} summary",
        extra={
            "message_count": metrics.get("message_count"),
            "total_interactions": metrics.get("total_interactions"),
            "avg_duration_seconds": metrics.get("avg_duration_seconds"),
            "avg_chunks_retrieved": metrics.get("avg_chunks_retrieved"),
            "avg_certainty_threshold": metrics.get("avg_certainty_threshold")
        }
    )
