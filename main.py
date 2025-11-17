import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timezone
from database import db, create_document, get_documents
from schemas import User, Couple, Invitation, CeremonyState, Certificate, ChatMessage

app = FastAPI(title="ShaadiVerse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "ShaadiVerse Backend Running"}

# --- Auth & Profile (simplified placeholder without Firebase) ---
class PhoneLoginIn(BaseModel):
    phone: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None

@app.post("/auth/phone")
def phone_login(payload: PhoneLoginIn):
    # Upsert user by phone
    existing = list(db["user"].find({"phone": payload.phone}).limit(1))
    if existing:
        user_id = str(existing[0]["_id"])
        db["user"].update_one({"_id": existing[0]["_id"]}, {"$set": {"name": payload.name or existing[0].get("name"), "avatar_url": payload.avatar_url or existing[0].get("avatar_url"), "gender": payload.gender or existing[0].get("gender"), "updated_at": datetime.now(timezone.utc)}})
    else:
        user = User(phone=payload.phone, name=payload.name, avatar_url=payload.avatar_url, gender=payload.gender)
        user_id = create_document("user", user)
    return {"user_id": user_id}

# --- Invitation Code & Pairing ---
class CreateInviteOut(BaseModel):
    code: str

import random, string

def _gen_code(n: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

@app.post("/invite/create", response_model=CreateInviteOut)
def create_invite(creator_user_id: str):
    code = _gen_code()
    inv = Invitation(code=code, creator_user_id=creator_user_id)
    _id = create_document("invitation", inv)
    return {"code": code}

class JoinByCodeIn(BaseModel):
    user_id: str
    code: str

@app.post("/invite/join")
def join_by_code(payload: JoinByCodeIn):
    inv = db["invitation"].find_one({"code": payload.code, "consumed": False})
    if not inv:
        raise HTTPException(status_code=404, detail="Invalid or used code")
    # create or fetch couple
    couple = None
    if inv.get("couple_id"):
        couple = db["couple"].find_one({"_id": inv["couple_id"]})
    if not couple:
        couple_doc = Couple(user_ids=[inv["creator_user_id"], payload.user_id])
        couple_id = create_document("couple", couple_doc)
        db["invitation"].update_one({"_id": inv["_id"]}, {"$set": {"consumed": True, "couple_id": couple_id}})
        # link users
        db["user"].update_many({"_id": {"$in": [inv["creator_user_id"], payload.user_id]}}, {"$set": {"couple_id": couple_id}})
    else:
        couple_id = str(couple["_id"])
        # add user if not present
        if payload.user_id not in couple.get("user_ids", []):
            db["couple"].update_one({"_id": couple["_id"]}, {"$addToSet": {"user_ids": payload.user_id}})
    return {"couple_id": couple_id}

# --- Ceremony State ---
class CeremonyInitIn(BaseModel):
    couple_id: str
    style: str

@app.post("/ceremony/init")
def ceremony_init(payload: CeremonyInitIn):
    st = CeremonyState(couple_id=payload.couple_id, step_key="ready", step_index=0, total_steps=7 if payload.style=="hindu" else 5, progress=0.0)
    _id = create_document("ceremonystate", st)
    db["couple"].update_one({"_id": payload.couple_id}, {"$set": {"wedding_style": payload.style}})
    return {"state_id": _id}

class CeremonyActionIn(BaseModel):
    couple_id: str
    action: str

@app.post("/ceremony/action")
def ceremony_action(payload: CeremonyActionIn):
    st = db["ceremonystate"].find_one({"couple_id": payload.couple_id}, sort=[("created_at", -1)])
    if not st:
        raise HTTPException(status_code=404, detail="No ceremony state")
    idx = st.get("step_index", 0) + 1
    total = st.get("total_steps", 7)
    progress = min(1.0, idx/max(1,total))
    db["ceremonystate"].update_one({"_id": st["_id"]}, {"$set": {"step_index": idx, "progress": progress, "step_key": payload.action, "updated_at": datetime.now(timezone.utc)}, "$push": {"log": {"ts": datetime.now(timezone.utc), "action": payload.action}}})
    return {"step_index": idx, "progress": progress}

# --- Chat (simplified) ---
class ChatIn(BaseModel):
    couple_id: str
    sender_id: str
    text: str

@app.post("/chat/send")
def chat_send(payload: ChatIn):
    msg = ChatMessage(couple_id=payload.couple_id, sender_id=payload.sender_id, text=payload.text, sent_at=datetime.now(timezone.utc))
    _id = create_document("chatmessage", msg)
    return {"message_id": _id}

@app.get("/chat/history")
def chat_history(couple_id: str, limit: int = 50):
    items = db["chatmessage"].find({"couple_id": couple_id}).sort("sent_at", -1).limit(limit)
    out = []
    for it in items:
        out.append({"id": str(it["_id"]), "sender_id": it["sender_id"], "text": it["text"], "sent_at": it.get("sent_at")})
    return list(reversed(out))

# --- Certificate (stub) ---
class CertRequest(BaseModel):
    couple_id: str
    couple_title: str
    theme: Optional[str] = None

@app.post("/certificate/generate")
def certificate_generate(req: CertRequest):
    cert = Certificate(couple_id=req.couple_id, couple_title=req.couple_title, wedding_date=datetime.now(timezone.utc), theme=req.theme, certificate_url=None)
    _id = create_document("certificate", cert)
    return {"certificate_id": _id}

# --- Simple health ---
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
