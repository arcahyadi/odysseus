# core/multi_model_manager.py
"""Multi-model thread lifecycle and persistence manager."""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import (
    SessionLocal, MultiModelThread, MultiModelMessage,
    Session as DbSession, ChatMessage as DbChatMessage, utcnow_naive
)
from core.session_manager import SessionManager
from src.auth_helpers import effective_user, get_current_user

logger = logging.getLogger(__name__)


class MultiModelThreadManager:
    """
    Manages multi-model thread lifecycle and persistence.

    Key responsibilities:
    - Create threads and persist to database
    - Add messages with proper indexing
    - Retrieve threads and messages grouped by model
    - List user threads
    - Delete threads and associated ephemeral sessions
    - Enforce ownership verification
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def _verify_ownership(self, thread: MultiModelThread, user: str) -> bool:
        """
        Verify that user owns the thread or can access it.

        Args:
            thread: MultiModelThread to check
            user: Current user ID from effective_user()

        Returns:
            True if user owns thread or thread is shared (null owner), False otherwise
        """
        if thread is None:
            return False
        
        # If owner is NULL, this is a shared thread visible to all
        if thread.owner is None:
            return True
        
        # Otherwise, user must match thread owner exactly
        return thread.owner == user

    def create_thread(
        self,
        owner: str,
        model_ids: List[str],
        endpoint_urls: Optional[List[str]],
        session_id: Optional[str] = None
    ) -> MultiModelThread:
        """
        Create a new multi-model thread.

        Args:
            owner: User ID (from effective_user) - REQUIRED, never NULL
            model_ids: List of model IDs to execute
            endpoint_urls: List of endpoint URLs (optional, resolved if not provided)
            session_id: Optional parent session ID for UI linking

        Returns:
            Created MultiModelThread object

        Note: Multi-model threads are ALWAYS user-owned (owner is never NULL).
        Shared threads are not supported for multi-model threads.
        """
        if not owner:
            raise ValueError("Owner must be specified for multi-model threads")

        thread_id = str(uuid.uuid4())

        # Validate session_id if provided
        if session_id:
            db = SessionLocal()
            try:
                existing = db.query(DbSession).filter(DbSession.id == session_id).first()
                if existing and existing.owner != owner:
                    raise ValueError(f"Session {session_id} not owned by {owner}")
            finally:
                db.close()

        db = SessionLocal()
        try:
            thread = MultiModelThread(
                id=thread_id,
                owner=owner,  # Always set owner - no shared threads
                model_ids=model_ids,
                endpoint_urls=endpoint_urls or [],
                session_id=session_id,
                created_at=utcnow_naive(),
                updated_at=utcnow_naive()
            )
            db.add(thread)
            db.commit()
            db.refresh(thread)
            return thread
        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to create thread: {e}")
        finally:
            db.close()

    def get_thread(self, thread_id: str) -> Optional[MultiModelThread]:
        """Retrieve a thread by ID."""
        db = SessionLocal()
        try:
            return db.query(MultiModelThread).filter(MultiModelThread.id == thread_id).first()
        finally:
            db.close()

    def get_thread_with_ownership_check(self, thread_id: str, user: str) -> Optional[MultiModelThread]:
        """
        Get thread with ownership verification.

        Args:
            thread_id: Thread to retrieve
            user: Current user from effective_user()

        Returns:
            Thread if found and user can access it, None otherwise
        """
        thread = self.get_thread(thread_id)
        if thread and self._verify_ownership(thread, user):
            return thread
        return None

    def add_message(
        self,
        thread_id: str,
        role: str,
        model_id: str,
        endpoint_url: str,
        content: str,
        message_index: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MultiModelMessage:
        """
        Add a message to the thread.

        Args:
            thread_id: Parent thread ID
            role: "user" or "assistant"
            model_id: Model that generated this message
            endpoint_url: Endpoint URL used
            content: Message content
            message_index: Position in thread (0-based, aligned across models)
            metadata: Optional JSON-serializable metadata

        Returns:
            Created MultiModelMessage object
        """
        db = SessionLocal()
        try:
            message = MultiModelMessage(
                id=str(uuid.uuid4()),
                thread_id=thread_id,
                model_id=model_id,
                endpoint_url=endpoint_url,
                role=role,
                content=content,
                meta_data=str(metadata) if metadata else None,
                timestamp=utcnow_naive(),
                message_index=message_index
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            return message
        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to add message: {e}")
        finally:
            db.close()

    def get_thread_messages(self, thread_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all messages for a thread, grouped by model.

        Returns:
            Dict mapping model_id -> list of message dicts
        """
        db = SessionLocal()
        try:
            messages = db.query(MultiModelMessage).filter(
                MultiModelMessage.thread_id == thread_id
            ).order_by(
                MultiModelMessage.model_id,
                MultiModelMessage.message_index,
                MultiModelMessage.timestamp
            ).all()

            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for msg in messages:
                if msg.model_id not in grouped:
                    grouped[msg.model_id] = []
                grouped[msg.model_id].append({
                    'id': msg.id,
                    'model_id': msg.model_id,
                    'endpoint_url': msg.endpoint_url,
                    'role': msg.role,
                    'content': msg.content,
                    'metadata': msg.meta_data,
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                    'message_index': msg.message_index
                })

            return grouped
        finally:
            db.close()

    def list_user_threads(self, owner: str) -> List[Dict[str, Any]]:
        """
        List all multi-model threads for a user.

        Args:
            owner: User ID from effective_user()

        Returns:
            List of thread info dicts with latest message info
        """
        db = SessionLocal()
        try:
            threads = db.query(MultiModelThread).filter(
                MultiModelThread.owner == owner
            ).order_by(
                MultiModelThread.created_at.desc()
            ).all()

            result = []
            for thread in threads:
                # Get latest message per model
                messages = db.query(MultiModelMessage).filter(
                    MultiModelMessage.thread_id == thread.id
                ).order_by(
                    MultiModelMessage.message_index.desc()
                ).all()

                latest_messages = {}
                for msg in messages:
                    if msg.model_id not in latest_messages:
                        latest_messages[msg.model_id] = msg.content[:100]

                result.append({
                    'id': thread.id,
                    'owner': thread.owner,
                    'model_ids': thread.model_ids,
                    'endpoint_urls': thread.endpoint_urls,
                    'session_id': thread.session_id,
                    'created_at': thread.created_at.isoformat() if thread.created_at else None,
                    'updated_at': thread.updated_at.isoformat() if thread.updated_at else None,
                    'latest_messages': latest_messages,
                    'message_count': len(messages)
                })

            return result
        finally:
            db.close()

    def delete_thread(self, thread_id: str, owner: str) -> bool:
        """
        Delete a thread and its associated ephemeral sessions.

        Args:
            thread_id: Thread to delete
            owner: User ID for ownership verification

        Returns:
            True if deleted, False if not found or unauthorized
        """
        db = SessionLocal()
        try:
            thread = db.query(MultiModelThread).filter(
                MultiModelThread.id == thread_id,
                MultiModelThread.owner == owner
            ).first()

            if not thread:
                return False

            # Delete messages first
            db.query(MultiModelMessage).filter(
                MultiModelMessage.thread_id == thread_id
            ).delete()

            # Get session IDs from thread data
            session_ids = []
            for mid in thread.model_ids:
                sid = f"[MM]{thread_id[:8]}-{mid[:8]}"
                session_ids.append(sid)

            # Delete ephemeral sessions
            for sid in session_ids:
                self.session_manager.delete_session(sid)

            # Delete thread
            db.delete(thread)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting thread {thread_id}: {e}")
            return False
        finally:
            db.close()

    def get_thread_for_session(self, session_id: str) -> Optional[MultiModelThread]:
        """Get multi-model thread by associated session ID."""
        db = SessionLocal()
        try:
            return db.query(MultiModelThread).filter(
                MultiModelThread.session_id == session_id
            ).first()
        finally:
            db.close()