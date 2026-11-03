# routes/multi_model_routes.py
"""Multi-model conversation thread routes."""

import json
import uuid
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Form
from pydantic import BaseModel

from core.database import SessionLocal, MultiModelThread, MultiModelMessage, utcnow_naive
from core.session_manager import SessionManager
from src.auth_helpers import effective_user, get_current_user
from routes.session_routes import _reject_raw_endpoint_url_for_non_admin, _verify_session_owner
from src.endpoint_resolver import normalize_base, build_headers, build_chat_url
from core.multi_model_manager import MultiModelThreadManager
from src.multi_model_executor import MultiModelExecutor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/multi-model", tags=["multi-model"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateThreadRequest(BaseModel):
    """Request model for creating a multi-model thread."""
    prompt: str
    model_ids: List[str]
    endpoint_urls: Optional[List[str]] = None
    session_id: Optional[str] = None
    use_web: bool = False
    use_research: bool = False


class CreateThreadResponse(BaseModel):
    """Response model for thread creation."""
    thread_id: str
    status: str
    models_executed: int


class ThreadResponse(BaseModel):
    """Response model for thread retrieval."""
    thread_id: str
    model_ids: List[str]
    endpoint_urls: List[str]
    session_id: Optional[str]
    created_at: str
    messages_by_model: Dict[str, List[Dict[str, Any]]]


class PartialFailureResponse(BaseModel):
    """
    Response model for partial failure scenarios.
    
    When some models succeed and others fail, the response includes:
    - status: "partial" if some succeeded, "complete" if all succeeded
    - results: dict mapping model_id -> success status and messages
    - errors: dict mapping model_id -> error code and message for failed models
    """
    thread_id: str
    status: str  # "complete" or "partial"
    results: Dict[str, Dict[str, Any]]
    errors: Dict[str, Dict[str, str]] = {}


# ============================================================================
# Route Handlers
# ============================================================================

def setup_multi_model_routes(session_manager: SessionManager):
    """Setup multi-model routes."""
    thread_manager = MultiModelThreadManager(session_manager)
    executor = MultiModelExecutor()

    @router.post("/", response_model=CreateThreadResponse)
    async def create_multi_model_thread(
        request: Request,
        prompt: str = Form(...),
        model_ids: str = Form(...),  # JSON list
        endpoint_urls: str = Form(None),  # JSON list, optional
        session_id: str = Form(None),
        use_web: str = Form("false"),
        use_research: str = Form("false"),
    ):
        """
        Create thread and execute prompt across models.

        Validates ownership, resolves endpoints, executes concurrently,
        and persists results to multi-model tables.

        For partial failures (some models succeed, some fail):
        - Successful models complete normally
        - Failed models have error details in the response
        - Thread is created with available results
        """
        # Get current user
        user = effective_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        # Parse model_ids from JSON string
        try:
            model_ids_list = json.loads(model_ids)
            if not isinstance(model_ids_list, list) or len(model_ids_list) < 2:
                raise HTTPException(400, "model_ids must be a JSON array with at least 2 models")
        except json.JSONDecodeError:
            raise HTTPException(400, "model_ids must be a valid JSON array")

        # Parse endpoint_urls if provided
        endpoint_urls_list = None
        if endpoint_urls:
            try:
                endpoint_urls_list = json.loads(endpoint_urls)
                if len(endpoint_urls_list) != len(model_ids_list):
                    raise HTTPException(400, "endpoint_urls must match model_ids count")
            except json.JSONDecodeError:
                raise HTTPException(400, "endpoint_urls must be a valid JSON array")

        # Validate session_id if provided
        if session_id:
            _verify_session_owner(request, session_id)

        # Create thread
        try:
            thread = thread_manager.create_thread(
                owner=user,
                model_ids=model_ids_list,
                endpoint_urls=endpoint_urls_list,
                session_id=session_id
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        # Build config with timeout
        config = {
            'timeout': 120,
            'use_web': use_web.lower() == "true",
            'use_research': use_research.lower() == "true"
        }

        # Execute across models
        try:
            results = await executor.execute_multi_model(
                prompt=prompt,
                model_ids=model_ids_list,
                endpoint_urls=endpoint_urls_list,
                headers={'Authorization': f"Bearer {get_current_user(request) or ''}"},
                config=config
            )
        except Exception as e:
            logger.error(f"Multi-model execution failed: {e}")
            raise HTTPException(500, f"Execution failed: {str(e)}")

        # Determine status based on results
        all_success = all(r['success'] for r in results.values())
        status = "complete" if all_success else "partial"

        # Persist messages
        try:
            for model_id, result in results.items():
                if result['success']:
                    for msg in result['messages']:
                        thread_manager.add_message(
                            thread_id=thread.id,
                            role=msg['role'],
                            model_id=model_id,
                            endpoint_url=result.get('endpoint_url', ''),
                            content=msg['content'],
                            message_index=msg.get('message_index', 0)
                        )
                else:
                    # Persist error message
                    thread_manager.add_message(
                        thread_id=thread.id,
                        role='assistant',
                        model_id=model_id,
                        endpoint_url='',
                        content=f"[Error: {result['error']['code']}] {result['error'].get('message', 'Unknown error')}",
                        message_index=0
                    )
        except Exception as e:
            logger.error(f"Failed to persist messages: {e}")
            # Don't fail the request - the execution succeeded, just persistence failed

        return CreateThreadResponse(
            thread_id=thread.id,
            status=status,
            models_executed=len(model_ids_list)
        )

    @router.get("/{thread_id}", response_model=ThreadResponse)
    async def get_multi_model_thread(
        request: Request,
        thread_id: str
    ):
        """
        Retrieve all messages from a multi-model thread.

        Verifies user owns the thread before returning.
        """
        # Get current user
        user = effective_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        # Get thread and verify ownership
        thread = thread_manager.get_thread_with_ownership_check(thread_id, user)
        if not thread:
            raise HTTPException(404, "Thread not found")

        # Get messages grouped by model
        messages_by_model = thread_manager.get_thread_messages(thread_id)

        return ThreadResponse(
            thread_id=thread.id,
            model_ids=thread.model_ids,
            endpoint_urls=thread.endpoint_urls,
            session_id=thread.session_id,
            created_at=thread.created_at.isoformat() if thread.created_at else None,
            messages_by_model=messages_by_model
        )

    @router.get("/", response_model=List[Dict[str, Any]])
    async def list_multi_model_threads(
        request: Request
    ):
        """
        List user's multi-model threads.
        """
        user = effective_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        threads = thread_manager.list_user_threads(user)
        return threads

    @router.delete("/{thread_id}")
    async def delete_multi_model_thread(
        request: Request,
        thread_id: str
    ):
        """
        Delete a multi-model thread and its associated sessions.
        """
        user = effective_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        # Verify thread exists and user owns it
        thread = thread_manager.get_thread_with_ownership_check(thread_id, user)
        if not thread:
            raise HTTPException(404, "Thread not found")

        deleted = thread_manager.delete_thread(thread_id, user)
        if deleted:
            return {"status": "deleted", "thread_id": thread_id}
        else:
            raise HTTPException(500, "Failed to delete thread")

    return router