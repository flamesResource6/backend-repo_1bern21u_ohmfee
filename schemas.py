"""
Database Schemas for ShaadiVerse

Each Pydantic model maps to a MongoDB collection using the lowercase
class name as the collection name.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

class User(BaseModel):
    phone: str = Field(..., description="E.164 phone number")
    name: Optional[str] = Field(None, description="Display name")
    avatar_url: Optional[str] = None
    gender: Optional[Literal["male","female","other"]] = None
    couple_id: Optional[str] = Field(None, description="Linked couple id if paired")
    theme_pref: Optional[str] = None

class Invitation(BaseModel):
    code: str = Field(..., description="6-8 char invite code")
    creator_user_id: str
    couple_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    consumed: bool = False

class Couple(BaseModel):
    title: Optional[str] = Field(None, description="Display title like Priya ❤️ Arjun")
    user_ids: List[str] = Field(default_factory=list)
    wedding_style: Optional[str] = Field(None, description="hindu|christian|muslim|sikh|south|western")
    wedding_date: Optional[datetime] = None
    ceremony_completed: bool = False

class CeremonyState(BaseModel):
    couple_id: str
    step_key: str = Field("idle", description="current ceremony step key")
    step_index: int = 0
    total_steps: int = 0
    progress: float = 0.0
    log: List[dict] = Field(default_factory=list)

class Certificate(BaseModel):
    couple_id: str
    couple_title: str
    wedding_date: datetime
    theme: Optional[str] = None
    certificate_url: Optional[str] = None

class ChatMessage(BaseModel):
    couple_id: str
    sender_id: str
    text: str
    sent_at: Optional[datetime] = None
