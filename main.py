import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Player, Room, Message

app = FastAPI(title="Ludo World API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Ludo World API"}

@app.get("/test")
def test_database():
    """Test endpoint to check database connectivity and list collections"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# ----- Helpers -----
class CreateRoomRequest(BaseModel):
    player_name: str
    room_code: Optional[str] = None

class JoinRoomRequest(BaseModel):
    player_name: str
    room_code: str

class RollDiceRequest(BaseModel):
    room_code: str
    player_id: str

from random import randint

def _collection(name: str):
    return db[name]

# Generate a simple 6-char code if not provided
import secrets
import string

def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))

# Assign colors in order
COLORS = ["red", "green", "yellow", "blue"]

def _next_color(players: List[dict]) -> str:
    used = {p.get("color") for p in players}
    for c in COLORS:
        if c not in used:
            return c
    return COLORS[len(players) % 4]

# ----- Core Endpoints -----
@app.post("/rooms/create")
def create_room(payload: CreateRoomRequest):
    rooms = _collection("room")
    code = payload.room_code or _generate_code()
    # Ensure unique
    if rooms.find_one({"code": code}):
        raise HTTPException(status_code=400, detail="Room code already exists")

    host_player = Player(name=payload.player_name, color=_next_color([]))
    room = Room(
        code=code,
        created_by="host",
        players=[{
            "_id": None,  # will be set after creation
            "name": host_player.name,
            "color": host_player.color,
            "tokens": host_player.tokens,
            "is_bot": host_player.is_bot,
        }],
        status="waiting"
    )

    inserted_id = rooms.insert_one(room.model_dump()).inserted_id
    # set player id as embedded generated id
    rooms.update_one({"_id": inserted_id}, {"$set": {"players.0._id": str(inserted_id) + "-p0"}})
    saved = rooms.find_one({"_id": inserted_id})
    saved["_id"] = str(saved["_id"])  # convert for json
    return saved

@app.post("/rooms/join")
def join_room(payload: JoinRoomRequest):
    rooms = _collection("room")
    room = rooms.find_one({"code": payload.room_code})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("status") != "waiting":
        raise HTTPException(status_code=400, detail="Game already started")
    players = room.get("players", [])
    if len(players) >= room.get("max_players", 4):
        raise HTTPException(status_code=400, detail="Room is full")

    color = _next_color(players)
    player_id = str(room["_id"]) + f"-p{len(players)}"
    players.append({
        "_id": player_id,
        "name": payload.player_name,
        "color": color,
        "tokens": [-1, -1, -1, -1],
        "is_bot": False
    })
    rooms.update_one({"_id": room["_id"]}, {"$set": {"players": players}})
    updated = rooms.find_one({"_id": room["_id"]})
    updated["_id"] = str(updated["_id"])  # convert for json
    return updated

@app.get("/rooms/{code}")
def get_room(code: str):
    rooms = _collection("room")
    room = rooms.find_one({"code": code})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    room["_id"] = str(room["_id"])  # to string
    return room

@app.post("/rooms/{code}/start")
def start_game(code: str):
    rooms = _collection("room")
    room = rooms.find_one({"code": code})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("status") != "waiting":
        raise HTTPException(status_code=400, detail="Already started")
    if len(room.get("players", [])) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 players")

    first_player_id = room["players"][0]["_id"]
    rooms.update_one({"_id": room["_id"]}, {"$set": {"status": "playing", "current_turn": first_player_id}})
    updated = rooms.find_one({"_id": room["_id"]})
    updated["_id"] = str(updated["_id"])  # convert
    return updated

@app.post("/rooms/{code}/roll")
def roll_dice(code: str, payload: RollDiceRequest):
    rooms = _collection("room")
    room = rooms.find_one({"code": code})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.get("status") != "playing":
        raise HTTPException(status_code=400, detail="Game not started")
    if room.get("current_turn") != payload.player_id:
        raise HTTPException(status_code=403, detail="Not your turn")

    roll = randint(1, 6)
    # store last roll
    rooms.update_one({"_id": room["_id"]}, {"$set": {"last_roll": roll}})

    # advance turn
    players = room.get("players", [])
    ids = [p.get("_id") for p in players]
    idx = ids.index(payload.player_id)
    next_id = ids[(idx + 1) % len(ids)]
    rooms.update_one({"_id": room["_id"]}, {"$set": {"current_turn": next_id}})

    updated = rooms.find_one({"_id": room["_id"]})
    updated["_id"] = str(updated["_id"])  # convert
    return {"roll": roll, "room": updated}

# Simple chat storage
class ChatPayload(BaseModel):
    room_code: str
    player_name: Optional[str] = None
    text: str

@app.post("/chat")
def post_chat(msg: ChatPayload):
    msgs = _collection("message")
    mid = msgs.insert_one({
        "room_code": msg.room_code,
        "player_name": msg.player_name,
        "text": msg.text,
    }).inserted_id
    return {"_id": str(mid)}

@app.get("/chat/{room_code}")
def get_chat(room_code: str):
    msgs = _collection("message")
    data = list(msgs.find({"room_code": room_code}).sort("_id", -1).limit(50))
    for d in data:
        d["_id"] = str(d["_id"])  # convert
    return list(reversed(data))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
