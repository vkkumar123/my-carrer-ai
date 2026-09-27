import io
import logging
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select

from app import storage
from app.api_schemas import ResumeOut
from app.auth import DB, CurrentUser
from app.config import get_settings
from app.llm import tasks
from app.llm.client import LLMError
from app.models import Resume

log = logging.getLogger(__name__)
router = APIRouter(prefix="/resumes", tags=["resumes"])

MIN_TEXT_CHARS = 200


def _extract_text(data: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except PdfReadError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unreadable PDF") from e
    return data.decode("utf-8", errors="ignore").strip()


def _out(r: Resume) -> ResumeOut:
    return ResumeOut(id=r.id, filename=r.filename, parsed=r.parsed, created_at=r.created_at)


@router.post("", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile, user: CurrentUser, db: DB) -> ResumeOut:
    filename = file.filename or "resume"
    if not filename.lower().endswith((".pdf", ".txt")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PDF or .txt file")
    max_bytes = get_settings().max_resume_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Resume file is too large")

    text = _extract_text(data, filename)
    if len(text) < MIN_TEXT_CHARS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Couldn't read enough text. Please upload a text-based (not scanned) PDF.",
        )
    try:
        parsed = tasks.parse_resume(text).model_dump()
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Resume analysis failed, try again") from e

    key = f"resumes/{user.id}/{uuid.uuid4()}-{filename[-100:]}"
    storage.save_file(key, data, file.content_type or "application/octet-stream")
    resume = Resume(user_id=user.id, filename=filename, storage_key=key, text=text, parsed=parsed)
    db.add(resume)
    db.commit()
    return _out(resume)


@router.get("", response_model=list[ResumeOut])
def list_resumes(user: CurrentUser, db: DB) -> list[ResumeOut]:
    rows = db.scalars(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    )
    return [_out(r) for r in rows]


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: str, user: CurrentUser, db: DB) -> None:
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    storage.delete_file(resume.storage_key)
    db.delete(resume)
    db.commit()
