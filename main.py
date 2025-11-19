import os
from datetime import datetime, timedelta, timezone
import secrets
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from bson import ObjectId
from hashlib import sha256

from database import db, create_document, get_documents

app = FastAPI(title="College Club App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers

def hash_password(password: str) -> str:
    salt = os.getenv("PASSWORD_SALT", "static_salt")
    return sha256(f"{salt}:{password}".encode()).hexdigest()

# Simple in-DB session handling using user.sessions list
SESSION_TTL_MINUTES = 60 * 24  # 1 day for demo

def new_session_token() -> str:
    return secrets.token_urlsafe(32)

# Request models
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ClubRequest(BaseModel):
    name: str
    description: Optional[str] = None

class EventRequest(BaseModel):
    title: str
    description: Optional[str] = None
    date: datetime
    club_id: Optional[str] = None

# Responses
class AuthResponse(BaseModel):
    token: str
    is_admin: bool
    name: str
    email: EmailStr

# Utilities

def get_user_by_email(email: str) -> Optional[Dict]:
    user = db["user"].find_one({"email": email})
    return user

def get_user_by_token(token: str) -> Optional[Dict]:
    if not token:
        return None
    user = db["user"].find_one({"sessions": token})
    return user

async def require_auth(token: Optional[str] = None):
    if token is None:
        raise HTTPException(status_code=401, detail="Missing token")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

async def require_admin(token: Optional[str] = None):
    user = await require_auth(token)
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")
    return user

@app.get("/")
def read_root():
    return {"message": "College Club API running"}

@app.post("/api/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    # Prevent duplicate emails
    if get_user_by_email(body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    # Create user; first user becomes admin for convenience
    is_first_user = db["user"].count_documents({}) == 0
    user_doc = {
        "name": body.name,
        "email": str(body.email),
        "password_hash": hash_password(body.password),
        "is_admin": is_first_user,
        "sessions": []
    }
    inserted_id = db["user"].insert_one(user_doc).inserted_id
    token = new_session_token()
    db["user"].update_one({"_id": inserted_id}, {"$push": {"sessions": token}})
    return AuthResponse(token=token, is_admin=is_first_user, name=user_doc["name"], email=user_doc["email"]) 

@app.post("/api/login", response_model=AuthResponse)
def login(body: LoginRequest):
    user = get_user_by_email(str(body.email))
    if not user or user.get("password_hash") != hash_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = new_session_token()
    db["user"].update_one({"_id": user["_id"]}, {"$push": {"sessions": token}})
    return AuthResponse(token=token, is_admin=user.get("is_admin", False), name=user.get("name", ""), email=user.get("email", ""))

@app.post("/api/logout")
def logout(token: Optional[str] = None):
    user = get_user_by_token(token or "")
    if user:
        db["user"].update_one({"_id": user["_id"]}, {"$pull": {"sessions": token}})
    return {"success": True}

# Clubs (admin only for create)
@app.get("/api/clubs")
def list_clubs():
    items = get_documents("club")
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.post("/api/clubs")
def create_club(body: ClubRequest, token: Optional[str] = None):
    user = get_user_by_token(token or "")
    if not user or not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")
    data = {
        "name": body.name,
        "description": body.description,
        "created_by": str(user.get("email"))
    }
    club_id = create_document("club", data)
    return {"id": club_id, **data}

# Events (admin only for create)
@app.get("/api/events")
def list_events():
    items = get_documents("event")
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.post("/api/events")
def create_event(body: EventRequest, token: Optional[str] = None):
    user = get_user_by_token(token or "")
    if not user or not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")
    data = {
        "title": body.title,
        "description": body.description,
        "date": body.date,
        "club_id": body.club_id,
        "created_by": str(user.get("email"))
    }
    event_id = create_document("event", data)
    return {"id": event_id, **data}

@app.get("/test")
def test_database():
    response = {"backend": "✅ Running"}
    try:
        collections = db.list_collection_names() if db else []
        response.update({
            "database": "✅ Connected & Working" if db else "❌ Not Available",
            "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
            "database_name": db.name if db else None,
            "connection_status": "Connected" if db else "Not Connected",
            "collections": collections[:10]
        })
    except Exception as e:
        response.update({"database": f"❌ Error: {str(e)[:50]}"})
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
