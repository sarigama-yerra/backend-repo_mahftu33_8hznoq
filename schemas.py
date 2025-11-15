"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# Example schemas (kept for reference):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: Optional[str] = Field(None, description="Email address")
    avatar: Optional[str] = Field(None, description="Avatar URL")
    coins: int = Field(100, description="In-game currency balance")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Ludo World specific schemas

class Player(BaseModel):
    name: str
    color: Literal["red", "green", "blue", "yellow"]
    # Positions for 4 tokens: -1 means in base, 0..56 on track, 57 means home
    tokens: List[int] = Field(default_factory=lambda: [-1, -1, -1, -1])
    is_bot: bool = False

class Room(BaseModel):
    code: str = Field(..., description="Join code")
    created_by: str = Field(..., description="Creator player id")
    status: Literal["waiting", "playing", "finished"] = "waiting"
    max_players: int = 4
    players: List[dict] = Field(default_factory=list, description="List of player dicts with _id, name, color, tokens")
    current_turn: Optional[str] = None  # player_id
    last_roll: Optional[int] = None

class Message(BaseModel):
    room_code: str
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    text: str
