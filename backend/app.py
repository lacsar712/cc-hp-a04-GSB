import json
import os
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from rules import judge

SECRET = os.environ.get("JWT_SECRET", "herb-process-dev-secret")
DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54393/herb")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
USERS = {
    "processor": {"role": "writer", "password_hash": pwd.hash("herb123456")},
    "checker": {"role": "reader", "password_hash": pwd.hash("check123456")},
}


def connect():
    return psycopg.connect(DSN, row_factory=dict_row)


class LoginIn(BaseModel):
    username: str
    password: str


class StepIn(BaseModel):
    name: str
    temp_c: float
    minutes: float


class BatchIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    steps: list[StepIn]
    chapter_id: int | None = None


class ChapterIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=200)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效令牌") from exc
    if payload.get("sub") not in USERS:
        raise HTTPException(status_code=401, detail="无效令牌")
    return {"username": payload["sub"], "role": payload.get("role")}


def require_writer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "writer":
        raise HTTPException(status_code=403, detail="仅炮制员可写入记录")
    return user


app = FastAPI(title="饮片炮制记录台")


@app.on_event("startup")
def startup():
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS chapters (
                id serial PRIMARY KEY,
                code text NOT NULL UNIQUE,
                summary text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS batches (
                id serial PRIMARY KEY,
                herb text NOT NULL,
                doc jsonb NOT NULL,
                verdict text NOT NULL,
                reason text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        conn.execute("ALTER TABLE batches ADD COLUMN IF NOT EXISTS chapter_code text")
        conn.execute("ALTER TABLE batches ADD COLUMN IF NOT EXISTS chapter_summary text")
        now = datetime.now(timezone.utc)
        chapter_count = conn.execute("SELECT COUNT(*) AS n FROM chapters").fetchone()["n"]
        if chapter_count == 0:
            conn.execute(
                """INSERT INTO chapters (code, summary, created_by, created_at)
                   VALUES (%s, %s, %s, %s)""",
                ("通则0213", "炮制通则：清炒温度80~150℃、时长5~30分钟，符合规定方可放行。", "processor", now),
            )
        count = conn.execute("SELECT COUNT(*) AS n FROM batches").fetchone()["n"]
        if count == 0:
            samples = [
                ("甘草", {"steps": [{"name": "清炒", "temp_c": 120, "minutes": 12}]}),
                ("黄芩", {"steps": [{"name": "清炒", "temp_c": 40, "minutes": 12}]}),
            ]
            for herb, doc in samples:
                verdict, reason = judge(doc)
                conn.execute(
                    """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
                       VALUES (%s, %s::jsonb, %s, %s, %s, %s)""",
                    (herb, json.dumps(doc, ensure_ascii=False), verdict, reason, "processor", now),
                )
        conn.commit()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "herb-process-record"}


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = USERS.get(body.username.strip())
    if not user or not pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": body.username.strip(), "role": user["role"], "exp": exp}, SECRET, algorithm="HS256")
    return {"access_token": token, "username": body.username.strip(), "role": user["role"]}


@app.get("/api/chapters")
def list_chapters(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, code, summary, created_by FROM chapters ORDER BY id"
        ).fetchall()
    return rows


@app.post("/api/chapters", status_code=201)
def create_chapter(body: ChapterIn, user: dict = Depends(require_writer)):
    code = body.code.strip()
    summary = body.summary.strip()
    if not code or not summary:
        raise HTTPException(status_code=400, detail="章节号与摘要句均不能为空")
    with connect() as conn:
        dup = conn.execute("SELECT id FROM chapters WHERE code = %s", (code,)).fetchone()
        if dup:
            raise HTTPException(status_code=409, detail="该章节号已录入章节簿")
        row = conn.execute(
            """INSERT INTO chapters (code, summary, created_by, created_at)
               VALUES (%s, %s, %s, %s)
               RETURNING id, code, summary, created_by""",
            (code, summary, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row


@app.delete("/api/chapters/{chapter_id}")
def delete_chapter(chapter_id: int, user: dict = Depends(require_writer)):
    with connect() as conn:
        row = conn.execute(
            "DELETE FROM chapters WHERE id = %s RETURNING id", (chapter_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="章节不存在")
        conn.commit()
    return {"deleted": chapter_id}


@app.get("/api/batches")
def list_batches(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, herb, doc, verdict, reason, created_by, chapter_code, chapter_summary
               FROM batches ORDER BY id DESC"""
        ).fetchall()
    return rows


@app.post("/api/batches", status_code=201)
def create_batch(body: BatchIn, user: dict = Depends(require_writer)):
    if body.chapter_id is None:
        raise HTTPException(status_code=400, detail="写入必须挑一条章节簿中已录入的药典章节")
    doc = {"steps": [s.model_dump() for s in body.steps]}
    verdict, reason = judge(doc)
    with connect() as conn:
        chapter = conn.execute(
            "SELECT id, code, summary FROM chapters WHERE id = %s", (body.chapter_id,)
        ).fetchone()
        if chapter is None:
            raise HTTPException(status_code=400, detail="所选章节不在章节簿中，可能已被删除")
        row = conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at, chapter_code, chapter_summary)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by, chapter_code, chapter_summary""",
            (
                body.herb.strip(),
                json.dumps(doc, ensure_ascii=False),
                verdict,
                reason,
                user["username"],
                datetime.now(timezone.utc),
                chapter["code"],
                chapter["summary"],
            ),
        ).fetchone()
        conn.commit()
    return row
