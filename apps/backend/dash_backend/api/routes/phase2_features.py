"""API routes for Phase 2+ features: email, security, voice, browser, collaboration, AI, infra."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from dash_backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/features", tags=["Features V2"])

# ── Email ──────────────────────────────────────────────────────────────────

@router.get("/email/accounts")
async def get_email_accounts(_user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import email_service
    return {"accounts": email_service.list_accounts()}

class EmailAccountReq(BaseModel):
    email: str
    provider: str = "imap"
    display_name: str = ""

@router.post("/email/accounts")
async def add_email_account(body: EmailAccountReq, _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import email_service
    return email_service.add_account(body.email, body.provider, body.display_name)

@router.get("/email/inbox")
async def get_inbox(limit: int = 50, unread_only: bool = False, _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import email_service
    return {"emails": email_service.get_inbox(limit, unread_only)}

@router.get("/email/search")
async def search_email(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import email_service
    return {"results": email_service.search(q)}

@router.get("/email/stats")
async def email_stats(_user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import email_service
    return email_service.get_stats()

# ── Calendar ───────────────────────────────────────────────────────────────

@router.get("/calendar/list")
async def list_calendars(_user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import calendar_service
    return {"calendars": calendar_service.list_calendars()}

class EventReq(BaseModel):
    title: str
    start: str
    end: str
    description: str = ""
    location: str = ""

@router.post("/calendar/events")
async def create_event(body: EventReq, _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import calendar_service
    return calendar_service.create_event(body.title, body.start, body.end, description=body.description, location=body.location)

@router.get("/calendar/events")
async def get_events(start: Optional[str] = None, end: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import calendar_service
    return {"events": calendar_service.get_events(start, end)}

@router.get("/calendar/upcoming")
async def get_upcoming(days: int = 7, _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import calendar_service
    return {"events": calendar_service.get_upcoming(days)}

@router.get("/calendar/stats")
async def calendar_stats(_user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import calendar_service
    return calendar_service.get_stats()

# ── Contacts ───────────────────────────────────────────────────────────────

class ContactReq(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    company: str = ""

@router.post("/contacts")
async def add_contact(body: ContactReq, _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import contact_service
    return contact_service.add_contact(body.name, body.email, body.phone, body.company)

@router.get("/contacts")
async def get_contacts(_user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import contact_service
    return {"contacts": contact_service.get_all()}

@router.get("/contacts/search")
async def search_contacts(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import contact_service
    return {"results": contact_service.search(q)}

@router.get("/contacts/stats")
async def contact_stats(_user=Depends(get_current_user)):
    from dash_backend.services.email_calendar import contact_service
    return contact_service.get_stats()

# ── 2FA (RFC 6238 TOTP) ────────────────────────────────────────────────────

@router.post("/security/2fa/enroll")
async def enroll_2fa(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import totp_service
    return totp_service.enroll(str(_user.id))

class TOTPVerifyReq(BaseModel):
    code: str
    confirm: bool = False

@router.post("/security/2fa/verify")
async def verify_2fa(body: TOTPVerifyReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import totp_service
    return totp_service.verify(str(_user.id), body.code, confirm=body.confirm)

@router.post("/security/2fa/enable")
async def enable_2fa(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import totp_service
    return totp_service.enable(str(_user.id))

@router.post("/security/2fa/disable")
async def disable_2fa(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import totp_service
    return totp_service.disable(str(_user.id))

@router.get("/security/2fa/status")
async def get_2fa_status(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import totp_service
    return totp_service.get_status(str(_user.id))

@router.post("/security/2fa/regenerate-backup")
async def regenerate_backup_codes(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import totp_service
    return totp_service.regenerate_backup_codes(str(_user.id))


# ── Biometric authentication (Windows Hello / Touch ID) ────────────────────

@router.get("/security/biometric/availability")
async def biometric_availability(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import biometric_service
    return biometric_service.availability()

@router.post("/security/biometric/enroll")
async def biometric_enroll(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import biometric_service
    return biometric_service.enroll(str(_user.id))

@router.get("/security/biometric/status")
async def biometric_status(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import biometric_service
    return biometric_service.get_status(str(_user.id))

class BiometricChallengeReq(BaseModel):
    action: str = "unlock"

@router.post("/security/biometric/challenge")
async def biometric_challenge(body: BiometricChallengeReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import biometric_service
    return biometric_service.create_challenge(str(_user.id), body.action)

class BiometricVerifyReq(BaseModel):
    challenge: str
    success: bool

@router.post("/security/biometric/verify")
async def biometric_verify(body: BiometricVerifyReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import biometric_service
    return biometric_service.verify_challenge(body.challenge, body.success, str(_user.id))

@router.post("/security/biometric/revoke")
async def biometric_revoke(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import biometric_service
    return biometric_service.revoke(str(_user.id))

@router.get("/security/biometric/audit")
async def biometric_audit(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import biometric_service
    return {"events": biometric_service.get_audit_log(str(_user.id))}


# ── Password Manager (AES-256-GCM vault) ─────────────────────────────────

class VaultEntryReq(BaseModel):
    category: str = "login"
    title: str
    fields: dict = {}
    notes: str = ""
    tags: list[str] = []

@router.post("/vault/entries")
async def add_vault_entry(body: VaultEntryReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    return password_manager.add_entry(body.category, body.title, body.fields, body.notes, body.tags)

@router.get("/vault/entries")
async def get_vault_entries(category: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    entries = password_manager.get_by_category(category) if category else password_manager.list_entries()
    return {"entries": entries}

class VaultUpdateReq(BaseModel):
    title: Optional[str] = None
    fields: Optional[dict] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    favorite: Optional[bool] = None

@router.patch("/vault/entries/{entry_id}")
async def update_vault_entry(entry_id: str, body: VaultUpdateReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    return password_manager.update_entry(entry_id, **changes)

@router.delete("/vault/entries/{entry_id}")
async def delete_vault_entry(entry_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    return password_manager.delete_entry(entry_id)

@router.get("/vault/entries/{entry_id}")
async def get_vault_entry(entry_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    entry = password_manager.get_entry(entry_id)
    if not entry:
        return {"ok": False, "reason": "Entry not found"}
    return {"ok": True, "entry": entry}

@router.get("/vault/search")
async def search_vault(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    return {"results": password_manager.search(q)}

@router.get("/vault/generate-password")
async def generate_password(length: int = 20, symbols: bool = True, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    return password_manager.generate_password(length, symbols)

@router.get("/vault/stats")
async def vault_stats(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import password_manager
    return password_manager.get_stats()

# ── Data Anonymization ─────────────────────────────────────────────────────

class AnonymizeReq(BaseModel):
    text: str
    mask_types: Optional[list[str]] = None

@router.post("/privacy/anonymize")
async def anonymize_text(body: AnonymizeReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import data_anonymizer
    return data_anonymizer.anonymize(body.text, body.mask_types)

@router.post("/privacy/scan")
async def scan_pii(body: AnonymizeReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import data_anonymizer
    return data_anonymizer.scan_text(body.text)


# ── Encrypted Messenger (AES-256-GCM, per-conversation keys) ───────────────

class MessageReq(BaseModel):
    recipient: str
    content: str

@router.post("/messenger/send")
async def send_message(body: MessageReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import encrypted_messenger
    sender = str(_user.id)
    return encrypted_messenger.send_message(sender, body.recipient, body.content)

class MessengerConversationReq(BaseModel):
    other_user: str

@router.post("/messenger/messages")
async def get_messenger_messages(body: MessengerConversationReq, _user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import encrypted_messenger
    me = str(_user.id)
    return {"messages": encrypted_messenger.get_messages(me, body.other_user)}

@router.get("/messenger/conversations")
async def get_conversations(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import encrypted_messenger
    return {"conversations": encrypted_messenger.get_conversations(str(_user.id))}

@router.get("/messenger/unread")
async def get_unread(_user=Depends(get_current_user)):
    from dash_backend.services.security_hardening import encrypted_messenger
    return {"unread": encrypted_messenger.get_unread_count(str(_user.id))}

# ── Voice ──────────────────────────────────────────────────────────────────

@router.get("/voice/config")
async def get_voice_config(_user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import voice_service
    return voice_service.get_config()

@router.get("/voice/commands")
async def get_voice_commands(_user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import voice_service
    return {"commands": voice_service.get_commands()}

@router.get("/voice/memos")
async def get_memos(limit: int = 20, _user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import voice_service
    return {"memos": voice_service.get_memos(limit)}

class MemoReq(BaseModel):
    title: str
    transcript: str
    duration_seconds: float = 0

@router.post("/voice/memos")
async def record_memo(body: MemoReq, _user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import voice_service
    return voice_service.record_memo(body.title, body.transcript, body.duration_seconds)

@router.get("/voice/stats")
async def voice_stats(_user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import voice_service
    return voice_service.get_stats()

# ── Browser ────────────────────────────────────────────────────────────────

@router.get("/browser/tabs")
async def get_tabs(_user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import browser_service
    return {"tabs": browser_service.get_tabs()}

class TabReq(BaseModel):
    url: str
    title: str = ""

@router.post("/browser/tabs/open")
async def open_tab(body: TabReq, _user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import browser_service
    return browser_service.open_tab(body.url, body.title)

@router.get("/browser/bookmarks")
async def get_bookmarks(folder: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import browser_service
    return {"bookmarks": browser_service.get_bookmarks(folder)}

@router.get("/browser/history")
async def get_history(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import browser_service
    return {"history": browser_service.get_history(limit)}

@router.get("/browser/stats")
async def browser_stats(_user=Depends(get_current_user)):
    from dash_backend.services.voice_browser import browser_service
    return browser_service.get_stats()

# ── Workspaces ─────────────────────────────────────────────────────────────

class WsReq(BaseModel):
    name: str
    description: str = ""

@router.post("/workspaces")
async def create_workspace(body: WsReq, _user=Depends(get_current_user)):
    from dash_backend.services.collaboration import workspace_service
    return workspace_service.create(body.name, str(id(_user)), body.description)

@router.get("/workspaces")
async def list_workspaces(_user=Depends(get_current_user)):
    from dash_backend.services.collaboration import workspace_service
    return {"workspaces": workspace_service.list_all()}

# ── Comments ───────────────────────────────────────────────────────────────

class CommentReq(BaseModel):
    entity_type: str
    entity_id: str
    content: str

@router.post("/comments")
async def add_comment(body: CommentReq, _user=Depends(get_current_user)):
    from dash_backend.services.collaboration import comment_service
    return comment_service.add(body.entity_type, body.entity_id, str(id(_user)), body.content)

@router.get("/comments/{entity_type}/{entity_id}")
async def get_comments(entity_type: str, entity_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.collaboration import comment_service
    return {"comments": comment_service.get_for_entity(entity_type, entity_id)}

# ── Prompt Studio ──────────────────────────────────────────────────────────

class PromptReq(BaseModel):
    name: str
    content: str
    category: str = "custom"

@router.post("/prompts")
async def create_prompt(body: PromptReq, _user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import prompt_studio
    return prompt_studio.create_prompt(body.name, body.content, body.category)

@router.get("/prompts")
async def list_prompts(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import prompt_studio
    return {"prompts": prompt_studio.get_all()}

@router.get("/prompts/templates")
async def get_templates(category: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import prompt_studio
    return {"templates": prompt_studio.get_templates(category)}

@router.get("/prompts/search")
async def search_prompts(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import prompt_studio
    return {"results": prompt_studio.search(q)}

# ── Model Evaluation ───────────────────────────────────────────────────────

@router.get("/evaluation/leaderboard")
async def get_leaderboard(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import model_evaluator
    return {"leaderboard": model_evaluator.get_leaderboard()}

@router.get("/evaluation/benchmarks")
async def get_benchmarks(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import model_evaluator
    return {"benchmarks": model_evaluator.get_benchmarks()}

# ── Learning ───────────────────────────────────────────────────────────────

@router.get("/learning/skills")
async def get_skills(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import learning_service
    return {"skills": learning_service.get_skills()}

@router.get("/learning/corrections")
async def get_corrections(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import learning_service
    return {"corrections": learning_service.get_corrections(limit)}

@router.get("/learning/stats")
async def learning_stats(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_ai import learning_service
    return learning_service.get_stats()

# ── Infrastructure ─────────────────────────────────────────────────────────

@router.get("/infra/circuit-breaker")
async def get_circuit_breakers(_user=Depends(get_current_user)):
    from dash_backend.services.infrastructure import circuit_breaker
    return {"breakers": circuit_breaker.get_all()}

@router.get("/infra/cache/stats")
async def get_cache_stats(_user=Depends(get_current_user)):
    from dash_backend.services.infrastructure import cache_service
    return cache_service.get_stats()

@router.post("/infra/cache/clear")
async def clear_cache(_user=Depends(get_current_user)):
    from dash_backend.services.infrastructure import cache_service
    return {"ok": True, "cleared": cache_service.clear()}

@router.get("/infra/health")
async def health_check_all(_user=Depends(get_current_user)):
    from dash_backend.services.infrastructure import health_check
    return health_check.check_all()

@router.get("/infra/health/{service}")
async def health_check_service(service: str, _user=Depends(get_current_user)):
    from dash_backend.services.infrastructure import health_check
    return health_check.check(service)
