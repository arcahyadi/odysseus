# src/multi_model_executor.py
"""Multi-model concurrent execution executor."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

import httpx

from core.database import SessionLocal
from src.endpoint_resolver import normalize_base, build_headers, build_chat_url
from routes.session_routes import _reject_raw_endpoint_url_for_non_admin
from src.auth_helpers import effective_user
from routes.compare_routes import _owned_endpoint_by_id, _owned_endpoint_by_url

logger = logging.getLogger(__name__)


class MultiModelExecutor:
    """
    Executes prompts across multiple models concurrently.

    Key features:
    - Limited concurrency (max_concurrent_requests=5)
    - Per-model timeout with asyncio.wait_for (120s default, configurable)
    - Error isolation: one model failure doesn't affect others
    - Respects registered endpoints for credential resolution
    - Supports mixed success scenarios (some models succeed, some fail)
    - Returns strict response schema for partial failure
    """

    def __init__(self, max_concurrent_requests: int = 5, default_timeout: int = 120, owner: str = None):
        """Initialize executor with concurrency and timeout limits.

        Args:
            max_concurrent_requests: Maximum concurrent model requests (default 5)
            default_timeout: Default timeout in seconds per model (default 120)
            owner: User owner for endpoint resolution
        """
        self.max_concurrent_requests = max_concurrent_requests
        self.default_timeout = default_timeout
        self.owner = owner  # For ownership verification in endpoint resolution

    async def execute_multi_model(
        self,
        prompt: str,
        model_ids: List[str],
        endpoint_urls: Optional[List[str]],
        headers: Dict[str, str],
        config: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute prompt across all models concurrently.

        Returns dict mapping model_id -> {
            'success': bool,
            'messages': List[Dict[str, Any]],
            'error': Optional[Dict[str, str]]
        }
        """
        timeout = config.get('timeout', self.default_timeout)

        # Resolve endpoints if not provided
        endpoints_resolved = []
        db = SessionLocal()
        try:
            user = effective_user(headers.get('Authorization', ''))

            for i, model_id in enumerate(model_ids):
                if endpoint_urls and i < len(endpoint_urls):
                    endpoint_url = endpoint_urls[i]
                    # Validate raw URL for non-admins
                    ep = _owned_endpoint_by_url(db, normalize_base(endpoint_url), user)
                    _reject_raw_endpoint_url_for_non_admin(
                        None, user, str(ep.id) if ep else None, endpoint_url
                    )
                    session_endpoint_url = (
                        build_chat_url(normalize_base(ep.base_url)) if ep else normalize_base(endpoint_url)
                    )
                    api_key = ep.api_key if ep else None
                else:
                    # Try to resolve from registered endpoint
                    ep = _owned_endpoint_by_id(db, model_id, user)
                    if ep is None:
                        endpoints_resolved.append({
                            'model_id': model_id,
                            'success': False,
                            'error': {'code': 'ENDPOINT_NOT_FOUND', 'message': f'Endpoint for {model_id} not found'}
                        })
                        continue
                    session_endpoint_url = build_chat_url(normalize_base(ep.base_url))
                    api_key = ep.api_key

                endpoints_resolved.append({
                    'model_id': model_id,
                    'endpoint_url': session_endpoint_url,
                    'api_key': api_key,
                    'headers': build_headers(api_key, session_endpoint_url) if api_key else None
                })
        finally:
            db.close()

        # Execute with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def execute_with_semaphore(model_idx: int, data: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self._execute_single_model(
                    model_id=data['model_id'],
                    endpoint_url=data['endpoint_url'],
                    prompt=prompt,
                    headers=data.get('headers') or {},
                    timeout=timeout
                )

        # Run all executions concurrently
        tasks = [
            execute_with_semaphore(i, data)
            for i, data in enumerate(endpoints_resolved)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build final result dict
        final_results = {}
        for i, data in enumerate(endpoints_resolved):
            model_id = data['model_id']
            result = results[i]

            if isinstance(result, Exception):
                final_results[model_id] = {
                    'success': False,
                    'messages': [],
                    'error': {'code': 'EXECUTION_ERROR', 'message': str(result)}
                }
            else:
                final_results[model_id] = result

        return final_results

    async def _execute_single_model(
        self,
        model_id: str,
        endpoint_url: str,
        prompt: str,
        headers: Dict[str, str],
        timeout: int
    ) -> Dict[str, Any]:
        """
        Execute single model call with error handling and timeout.

        Uses the same chat_stream pattern as compare mode.
        """
        try:
            async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
                # Build request payload matching /api/chat_stream
                payload = {
                    'model': model_id,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'stream': True
                }

                response = await client.post(
                    f"{endpoint_url}/chat/completions",
                    json=payload
                )
                response.raise_for_status()

                # Collect streaming response
                messages = []
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith('data: '):
                        data = line[6:]
                        if data.strip() == '[DONE]':
                            break
                        try:
                            import json
                            chunk = json.loads(data)
                            if chunk.get('choices'):
                                content = chunk['choices'][0].get('delta', {}).get('content', '')
                                if content:
                                    if not messages:
                                        messages.append({'role': 'assistant', 'content': ''})
                                    messages[-1]['content'] += content
                        except json.JSONDecodeError:
                            continue

                return {
                    'success': True,
                    'messages': messages,
                    'error': None
                }

        except asyncio.TimeoutError:
            return {
                'success': False,
                'messages': [],
                'error': {'code': 'TIMEOUT', 'message': f'Request timed out after {timeout}s'}
            }
        except httpx.HTTPStatusError as e:
            return {
                'success': False,
                'messages': [],
                'error': {'code': 'HTTP_ERROR', 'message': f'HTTP {e.response.status_code}: {e.response.text}'}
            }
        except httpx.RequestError as e:
            return {
                'success': False,
                'messages': [],
                'error': {'code': 'NETWORK_ERROR', 'message': str(e)}
            }
        except Exception as e:
            return {
                'success': False,
                'messages': [],
                'error': {'code': 'UNKNOWN_ERROR', 'message': str(e)}
            }