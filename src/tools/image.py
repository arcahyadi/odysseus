"""Image-domain tool implementations.

Extracted from tool_implementations.py as part of slice 1 (#4082/#4071).
Holds the edit_image (gallery) tool.
``src.tool_implementations`` re-exports these for backward compatibility.
``_INTERNAL_BASE`` still lives in tool_implementations.py and is pulled back
function-locally here.
"""
from typing import Dict, Optional

from src.tools._common import _parse_tool_args


async def do_edit_image(content: str, owner: Optional[str] = None) -> Dict:
    """Edit a gallery image (upscale, rembg, inpaint, harmonize)."""
    import httpx
    from src.tool_implementations import _INTERNAL_BASE  # shared constant, still lives in the facade
    try:
        args = _parse_tool_args(content)
    except ValueError:
        return {"error": "Invalid JSON arguments", "exit_code": 1}
    image_id = args.get("image_id", "")
    action = args.get("action", "")
    if not image_id or not action:
        return {"error": "image_id and action are required", "exit_code": 1}
    payload = {"image_id": image_id}
    if args.get("prompt"):
        payload["prompt"] = args["prompt"]
    if args.get("scale"):
        payload["scale"] = args["scale"]
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{_INTERNAL_BASE}/api/gallery/{action}", json=payload)
            data = resp.json()
        new_id = data.get("id") or data.get("image_id")
        if data.get("success") or new_id:
            result = {
                "output": f"Image edited ({action}). New image ID: {new_id or '?'}",
                "exit_code": 0,
            }
            if new_id:
                result["image_id"] = new_id
                try:
                    from src.database import GalleryImage, SessionLocal
                    db = SessionLocal()
                    try:
                        q = db.query(GalleryImage).filter(GalleryImage.id == new_id)
                        if owner:
                            q = q.filter(GalleryImage.owner == owner)
                        img = q.first()
                        if img and img.filename:
                            result.update({
                                "image_url": f"/api/generated-image/{img.filename}",
                                "image_prompt": img.prompt or args.get("prompt") or action,
                                "image_model": img.model or "edit_image",
                                "image_size": img.size or "",
                                "image_quality": img.quality or "",
                            })
                    finally:
                        db.close()
                except Exception:
                    pass
            return result
        return {"error": data.get("error", f"{action} failed"), "exit_code": 1}
    except Exception as e:
        return {"error": str(e), "exit_code": 1}
