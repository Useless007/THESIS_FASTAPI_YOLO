# app/services/ws_manager.py
from typing import List
from fastapi import WebSocket
from pydantic import BaseModel

admin_connections: List[WebSocket] = []

class NotifyPayload(BaseModel):
    order_id: int
    reason: str

async def notify_admin(order_id: int, reason: str):
    message = {
        "order_id": order_id,
        "message": f"⚠️ ออเดอร์ #{order_id} ถูกเปลี่ยนเป็น PENDING - {reason}",
    }
    for connection in admin_connections:
        await connection.send_json(message)
