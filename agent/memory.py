"""
Memory management module using SQLite for conversation history storage.
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import os


class MemoryManager:
    """Manages conversation memory using SQLite database."""

    def __init__(self, db_path: str = "agent_memory.db"):
        """
        Initialize memory manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)

            # Create messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)

            # Create index on session_id for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                ON messages(session_id)
            """)

            # Create interactions table for tracking retrieval and answers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message_id INTEGER,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    chunks_retrieved INTEGER,
                    certainty_threshold REAL,
                    limit_used INTEGER,
                    sources TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_seconds REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
                    FOREIGN KEY (message_id) REFERENCES messages (message_id)
                )
            """)

            # Create metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)

            conn.commit()

    def create_session(self, session_id: str, user_id: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new conversation session.

        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
            metadata: Optional metadata dictionary

        Returns:
            session_id
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_id, user_id, metadata)
                VALUES (?, ?, ?)
            """, (
                session_id,
                user_id,
                json.dumps(metadata) if metadata else None
            ))
            return session_id

    def add_message(self, session_id: str, role: str, content: str,
                   metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add a message to the conversation history.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata

        Returns:
            message_id
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
            """, (
                session_id,
                role,
                content,
                json.dumps(metadata) if metadata else None
            ))

            # Update session timestamp
            cursor.execute("""
                UPDATE sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))

            return cursor.lastrowid

    def get_conversation_history(self, session_id: str,
                                limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Optional limit on number of messages to retrieve

        Returns:
            List of message dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT message_id, role, content, timestamp, metadata
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, (session_id,))

            messages = []
            for row in cursor.fetchall():
                messages.append({
                    "message_id": row["message_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None
                })

            return messages

    def add_interaction(self, session_id: str, query: str, answer: str,
                       chunks_retrieved: int, certainty_threshold: float,
                       limit_used: int, sources: List[Dict[str, Any]],
                       duration_seconds: float, message_id: Optional[int] = None) -> int:
        """
        Record an interaction (query-answer pair with retrieval metadata).

        Args:
            session_id: Session identifier
            query: User query
            answer: Generated answer
            chunks_retrieved: Number of chunks retrieved
            certainty_threshold: Certainty threshold used
            limit_used: Limit parameter used
            sources: List of source chunks
            duration_seconds: Time taken for the interaction
            message_id: Optional associated message ID

        Returns:
            interaction_id
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO interactions (
                    session_id, message_id, query, answer,
                    chunks_retrieved, certainty_threshold, limit_used,
                    sources, duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                message_id,
                query,
                answer,
                chunks_retrieved,
                certainty_threshold,
                limit_used,
                json.dumps(sources),
                duration_seconds
            ))

            return cursor.lastrowid

    def get_session_interactions(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all interactions for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of interaction dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM interactions
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))

            interactions = []
            for row in cursor.fetchall():
                interactions.append({
                    "interaction_id": row["interaction_id"],
                    "query": row["query"],
                    "answer": row["answer"],
                    "chunks_retrieved": row["chunks_retrieved"],
                    "certainty_threshold": row["certainty_threshold"],
                    "limit_used": row["limit_used"],
                    "sources": json.loads(row["sources"]) if row["sources"] else [],
                    "timestamp": row["timestamp"],
                    "duration_seconds": row["duration_seconds"]
                })

            return interactions

    def record_metric(self, metric_name: str, metric_value: float,
                     session_id: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """
        Record a metric value.

        Args:
            metric_name: Name of the metric
            metric_value: Value of the metric
            session_id: Optional session identifier
            metadata: Optional metadata
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metrics (session_id, metric_name, metric_value, metadata)
                VALUES (?, ?, ?, ?)
            """, (
                session_id,
                metric_name,
                metric_value,
                json.dumps(metadata) if metadata else None
            ))

    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """
        Get aggregated metrics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with metric statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get interaction metrics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_interactions,
                    AVG(duration_seconds) as avg_duration,
                    AVG(chunks_retrieved) as avg_chunks,
                    AVG(certainty_threshold) as avg_certainty
                FROM interactions
                WHERE session_id = ?
            """, (session_id,))

            interaction_stats = dict(cursor.fetchone())

            # Get message count
            cursor.execute("""
                SELECT COUNT(*) as message_count
                FROM messages
                WHERE session_id = ?
            """, (session_id,))

            message_count = cursor.fetchone()["message_count"]

            return {
                "message_count": message_count,
                "total_interactions": interaction_stats["total_interactions"],
                "avg_duration_seconds": interaction_stats["avg_duration"],
                "avg_chunks_retrieved": interaction_stats["avg_chunks"],
                "avg_certainty_threshold": interaction_stats["avg_certainty"]
            }

    def get_all_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all sessions.

        Args:
            limit: Maximum number of sessions to retrieve

        Returns:
            List of session dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    s.session_id,
                    s.user_id,
                    s.created_at,
                    s.updated_at,
                    s.metadata,
                    COUNT(m.message_id) as message_count
                FROM sessions s
                LEFT JOIN messages m ON s.session_id = m.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT ?
            """, (limit,))

            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    "session_id": row["session_id"],
                    "user_id": row["user_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                    "message_count": row["message_count"]
                })

            return sessions

    def clear_session(self, session_id: str):
        """
        Clear all data for a specific session.

        Args:
            session_id: Session identifier
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM interactions WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM metrics WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def get_database_stats(self) -> Dict[str, int]:
        """
        Get overall database statistics.

        Returns:
            Dictionary with database statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Count sessions
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            stats["total_sessions"] = cursor.fetchone()["count"]

            # Count messages
            cursor.execute("SELECT COUNT(*) as count FROM messages")
            stats["total_messages"] = cursor.fetchone()["count"]

            # Count interactions
            cursor.execute("SELECT COUNT(*) as count FROM interactions")
            stats["total_interactions"] = cursor.fetchone()["count"]

            # Get database size
            stats["db_size_bytes"] = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

            return stats
