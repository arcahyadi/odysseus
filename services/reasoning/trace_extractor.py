import re
from typing import AsyncGenerator

# Matches <think>...</think> blocks (non-greedy, multi-block, case-insensitive)
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def extract_thinking(text: str) -> tuple[str, list[str]]:
    """
    Extract all <think>...</think> blocks from text.
    Returns (clean_text, list_of_think_segments).
    clean_text has all <think> blocks removed and stripped.
    Requirements: 9.1
    """
    segments = [seg.strip() for seg in _THINK_RE.findall(text)]
    clean_text = _THINK_RE.sub("", text).strip()
    return clean_text, segments


def extract_thinking_streaming(accumulated: str) -> tuple[str, list[str], bool]:
    """
    For use during SSE streaming.
    Returns (clean_so_far, segments_found, has_open_think).
    has_open_think = True if <think> has been seen but </think> not yet.
    Requirements: 10.5
    """
    segments = [seg.strip() for seg in _THINK_RE.findall(accumulated)]
    clean_so_far = _THINK_RE.sub("", accumulated).strip()
    has_open_think = (
        "<think>" in accumulated.lower() and "</think>" not in accumulated.lower()
    )
    return clean_so_far, segments, has_open_think


async def reasoning_aware_stream(
    base_generator: AsyncGenerator,
) -> AsyncGenerator:
    """
    Async generator wrapper that:
    1. Buffers tokens looking for <think> blocks
    2. Emits {"type": "thinking_node", "index": N, "content": "..."} events for each complete think block
    3. Forwards cleaned content as {"type": "content", "token": "..."} events
    Requirements: 9.1, 10.5
    """
    buf = ""
    think_buf = ""
    in_think = False
    node_index = 0

    async for chunk in base_generator:
        if not isinstance(chunk, dict) or chunk.get("type") != "content":
            yield chunk
            continue
        token = chunk.get("token", "")
        buf += token

        while True:
            if not in_think:
                open_pos = buf.lower().find("<think>")
                if open_pos == -1:
                    # No open tag — emit safe portion (leave last 7 chars buffered)
                    safe = buf[:-7] if len(buf) > 7 else ""
                    if safe:
                        yield {"type": "content", "token": safe}
                        buf = buf[len(safe):]
                    break
                else:
                    if open_pos > 0:
                        yield {"type": "content", "token": buf[:open_pos]}
                    buf = buf[open_pos + 7:]
                    in_think = True
            else:
                close_pos = buf.lower().find("</think>")
                if close_pos == -1:
                    if len(buf) > 8:
                        think_buf += buf[:-8]
                        buf = buf[-8:]
                    break
                else:
                    think_buf += buf[:close_pos]
                    yield {"type": "thinking_node", "index": node_index, "content": think_buf.strip()}
                    node_index += 1
                    buf = buf[close_pos + 8:]
                    think_buf = ""
                    in_think = False

    # Flush remaining
    if buf and not in_think:
        yield {"type": "content", "token": buf}
