from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/channels", tags=["channels"])


class SendMessageRequest(BaseModel):
    channel: str  # "discord", "telegram", "email"
    recipient_id: str
    content: str


class BroadcastRequest(BaseModel):
    content: str
    channels: list[str] | None = None


@router.post("/send")
async def send_message(req: SendMessageRequest):
    """Envoie un message via un canal spécifique."""
    try:
        from src.channel_gateway import ChannelType, OutboundMessage, get_gateway

        gateway = get_gateway()
        ch = ChannelType(req.channel)
        msg = OutboundMessage(channel=ch, recipient_id=req.recipient_id, content=req.content)
        ok = await gateway.send(msg)
        return {"ok": ok, "channel": req.channel}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/broadcast")
async def broadcast(req: BroadcastRequest):
    """Broadcast vers plusieurs canaux."""
    try:
        from src.channel_gateway import ChannelType, get_gateway

        gateway = get_gateway()
        channels = [ChannelType(c) for c in req.channels] if req.channels else None
        results = await gateway.broadcast(req.content, channels)
        return {"ok": True, "results": results}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/status")
async def channel_status():
    """Liste les adapters enregistrés et leur statut."""
    try:
        from src.channel_gateway import get_gateway

        gateway = get_gateway()
        return {"adapters": [ch.value for ch in gateway._adapters.keys()], "count": len(gateway._adapters)}
    except Exception as e:
        return {"error": str(e)}


@router.get("")
async def channel_root():
    """Root endpoint for channels."""
    return {"channels": [], "status": "ok"}
