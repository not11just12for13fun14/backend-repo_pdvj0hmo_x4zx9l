"""
Database Schemas for College Club App

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password (server-side only)")
    is_admin: bool = Field(False, description="Admin privileges")
    sessions: Optional[List[str]] = Field(default_factory=list, description="Active session tokens")

class Club(BaseModel):
    name: str = Field(..., description="Club name")
    description: Optional[str] = Field(None, description="Short description")
    created_by: Optional[str] = Field(None, description="User id or email of the creator")

class Event(BaseModel):
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event details")
    date: datetime = Field(..., description="Event date and time (ISO 8601)")
    club_id: Optional[str] = Field(None, description="Related club id (string)")
    created_by: Optional[str] = Field(None, description="User id or email of the creator")
