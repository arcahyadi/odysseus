import logging
import uuid
from typing import Optional
from sqlalchemy.orm import joinedload
from core.database import ReasoningTrace, ReasoningNode, SessionLocal, utcnow_naive

logger = logging.getLogger(__name__)


class TraceStore:
    def persist(
        self,
        session_id: str,
        message_id: str,
        owner: str,
        model: str,
        segments: list[str],
    ) -> Optional[ReasoningTrace]:
        """
        Write a ReasoningTrace + N ReasoningNodes in one transaction.
        Returns None if segments is empty or all-whitespace.
        Requirements: 9.2, 9.3, 9.5
        """
        # Filter out blank segments
        non_empty = [s for s in segments if s and s.strip()]
        if not non_empty:
            return None

        db = SessionLocal()
        try:
            trace = ReasoningTrace(
                id=str(uuid.uuid4()),
                session_id=session_id,
                message_id=message_id,
                owner=owner,
                model=model,
                full_text="\n\n".join(non_empty),
            )
            db.add(trace)

            for idx, seg in enumerate(non_empty):
                node = ReasoningNode(
                    id=str(uuid.uuid4()),
                    trace_id=trace.id,
                    index=idx,
                    content=seg,
                )
                db.add(node)

            db.commit()
            db.refresh(trace)
            return trace
        except Exception:
            db.rollback()
            logger.exception("TraceStore.persist failed for message_id=%s", message_id)
            raise
        finally:
            db.close()

    def get_for_message(self, message_id: str) -> Optional[ReasoningTrace]:
        """
        Return ReasoningTrace with eagerly loaded nodes for a message_id, or None.
        Requirements: 9.4
        """
        db = SessionLocal()
        try:
            return (
                db.query(ReasoningTrace)
                .options(joinedload(ReasoningTrace.nodes))
                .filter(ReasoningTrace.message_id == message_id)
                .first()
            )
        finally:
            db.close()

    def list_for_session(self, session_id: str) -> list:
        """
        Return all ReasoningTrace records for a session (without node content),
        ordered by created_at descending.
        Requirements: 9.4
        """
        db = SessionLocal()
        try:
            return (
                db.query(ReasoningTrace)
                .filter(ReasoningTrace.session_id == session_id)
                .order_by(ReasoningTrace.created_at.desc())
                .all()
            )
        finally:
            db.close()


# Module-level singleton
trace_store = TraceStore()
