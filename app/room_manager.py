"""Room manager stub — full implementation pending from macOS."""

ROOMS = {}

async def handle_room_ws(websocket, room_id: str):
    await websocket.accept()
    await websocket.send_json({"type": "info", "message": f"Room {room_id}: stub mode"})
    await websocket.close()

def create_room(scene_id: str) -> str:
    import uuid
    room_id = f"room_{uuid.uuid4().hex[:8]}"
    ROOMS[room_id] = {"scene_id": scene_id, "clients": []}
    return room_id

def get_room_info(room_id: str) -> dict:
    if room_id not in ROOMS:
        return {"error": "Room not found"}
    return {"room_id": room_id, **ROOMS[room_id]}

def list_active_rooms() -> list:
    return [{"room_id": rid, "scene_id": r["scene_id"]} for rid, r in ROOMS.items()]
