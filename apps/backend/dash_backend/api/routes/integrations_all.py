# -*- coding: utf-8 -*-
"""API Routes for OAuth, Integrations, Voice Engine, Browser Automation, Push Notifications.

Security (decisions.md #38): this router was previously mounted with NO
authentication — anonymous clients could read and delete browser bookmarks,
voice memos, notification channels/templates, relay devices, and webhook
registrations. Router-level auth now protects every endpoint here; the
verified platform webhook receivers live in integration_connectors.py,
which deliberately stays unauthenticated (platform credential = auth).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from dash_backend.auth.dependencies import get_current_user

# Router-wide auth: every route in this module requires a valid DASH token.
# Handlers that need the identity can still add Depends(get_current_user)
# individually; FastAPI caches the dependency per-request.
router = APIRouter(dependencies=[Depends(get_current_user)])


# ── Request Models ───────────────────────────────────────────────────────────

class OAuthConfigure(BaseModel):
    provider: str
    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:3000/auth/callback"

class OAuthExchange(BaseModel):
    provider: str
    code: str
    state: str

class IntegrationConfigure(BaseModel):
    service: str
    api_key: str = ""
    webhook_url: str = ""
    bot_token: str = ""
    channel_id: str = ""
    enabled: bool = True

class IntegrationMessage(BaseModel):
    service: str
    channel: str
    content: str
    author: str = "DASH"

class WebhookCreate(BaseModel):
    service: str
    url: str
    events: list[str]

class VoiceSTTConfig(BaseModel):
    language: str = "en"
    model: str = "base"

class VoiceTTSConfig(BaseModel):
    voice: str = "default"
    rate: float = 1.0
    pitch: float = 1.0

class WakeWordConfig(BaseModel):
    enabled: bool = True
    sensitivity: float = 0.7

class VoiceTranscribe(BaseModel):
    text_hint: str = ""

class VoiceSynthesize(BaseModel):
    text: str
    voice: str = "default"

class VoiceCommandParse(BaseModel):
    text: str

class VoiceMemoCreate(BaseModel):
    text: str
    duration: float = 0.0
    language: str = "en"
    tags: list[str] = []

class TabOpen(BaseModel):
    url: str
    title: str = ""
    active: bool = False

class BookmarkCreate(BaseModel):
    url: str
    title: str
    folder: str = "Bookmarks Bar"
    tags: list[str] = []

class ReadingListAdd(BaseModel):
    url: str
    title: str
    priority: str = "medium"

class NotifSend(BaseModel):
    title: str
    body: str
    channel: str = "default"
    priority: str = "normal"
    data: dict = {}
    image_url: str = ""
    action_url: str = ""
    scheduled_at: str = ""

class NotifChannelCreate(BaseModel):
    name: str
    type: str
    config: dict = {}

class NotifTemplateCreate(BaseModel):
    name: str
    title_template: str
    body_template: str
    channel: str = "default"
    schedule: str = ""

class DeviceRegister(BaseModel):
    device_id: str
    platform: str
    token: str = ""

class NotifPrefs(BaseModel):
    channels: dict = {"push": True, "email": False}
    priority_filter: str = "normal"
    sound_enabled: bool = True

class QuietHours(BaseModel):
    start_hour: int = 23
    end_hour: int = 7


# ═════════════════════════════════════════════════════════════════════════════
# OAUTH SOCIAL LOGIN
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/oauth/configure")
async def oauth_configure(body: OAuthConfigure):
    from dash_backend.services.oauth_social import get_oauth_service
    return get_oauth_service().configure_provider(
        body.provider, body.client_id, body.client_secret, body.redirect_uri
    )

@router.get("/oauth/providers")
async def oauth_providers():
    from dash_backend.services.oauth_social import get_oauth_service
    return get_oauth_service().get_configured_providers()

@router.get("/oauth/providers/{provider}")
async def oauth_provider_info(provider: str):
    from dash_backend.services.oauth_social import get_oauth_service
    try:
        return get_oauth_service().get_provider_info(provider)
    except ValueError as exc:
        # Unknown provider is a client error, not a server fault.
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/oauth/authorize/{provider}")
async def oauth_authorize(provider: str, redirect_uri: str = None):
    from dash_backend.services.oauth_social import get_oauth_service
    try:
        return get_oauth_service().get_authorize_url(provider, redirect_uri)
    except ValueError as exc:
        # Unknown/unconfigured provider is a client error, not a server fault.
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.post("/oauth/exchange")
async def oauth_exchange(body: OAuthExchange):
    from dash_backend.services.oauth_social import get_oauth_service
    try:
        return await get_oauth_service().exchange_code(body.provider, body.code, body.state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/oauth/link/{user_id}")
async def oauth_link(user_id: str, provider: str, user_info: dict = {}):
    from dash_backend.services.oauth_social import get_oauth_service
    return get_oauth_service().link_account(user_id, provider, user_info)

@router.post("/oauth/unlink/{user_id}")
async def oauth_unlink(user_id: str, provider: str):
    from dash_backend.services.oauth_social import get_oauth_service
    return get_oauth_service().unlink_account(user_id, provider)

@router.get("/oauth/accounts/{user_id}")
async def oauth_accounts(user_id: str):
    from dash_backend.services.oauth_social import get_oauth_service
    return get_oauth_service().get_linked_accounts(user_id)


# ═════════════════════════════════════════════════════════════════════════════
# EXTERNAL INTEGRATIONS (Slack, Telegram, GitHub, Notion, Discord, Twitter)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/integrations")
async def integrations_status():
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().get_integrations_status()

@router.post("/integrations/configure")
async def integrations_configure(body: IntegrationConfigure):
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().configure(
        body.service, api_key=body.api_key, webhook_url=body.webhook_url,
        bot_token=body.bot_token, channel_id=body.channel_id, enabled=body.enabled,
    )

@router.post("/integrations/send")
async def integrations_send(body: IntegrationMessage):
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().send_message(body.service, body.channel, body.content, body.author)

@router.get("/integrations/messages/{service}")
async def integrations_messages(service: str, channel: str = None, limit: int = 50):
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().get_messages(service, channel, limit)

@router.post("/integrations/webhooks")
async def integrations_webhook_create(body: WebhookCreate):
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().create_webhook(body.service, body.url, body.events)

@router.get("/integrations/webhooks")
async def integrations_webhooks(service: str = None):
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().get_webhooks(service)

@router.delete("/integrations/webhooks/{webhook_id}")
async def integrations_webhook_delete(webhook_id: str):
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().delete_webhook(webhook_id)

@router.get("/integrations/events")
async def integrations_events(limit: int = 100):
    from dash_backend.services.integrations import get_integration_service
    return get_integration_service().get_events(limit)


# ═════════════════════════════════════════════════════════════════════════════
# VOICE ENGINE
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/voice/status")
async def voice_status():
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().get_status()

@router.post("/voice/wake-word/configure")
async def voice_wake_word_configure(body: WakeWordConfig):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().configure_wake_word(body.enabled, body.sensitivity)

@router.post("/voice/wake-word/detect")
async def voice_wake_word_detect(text: str):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().detect_wake_word(text)

@router.get("/voice/wake-word/detections")
async def voice_wake_word_detections(limit: int = 50):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().get_wake_word_detections(limit)

@router.post("/voice/stt/configure")
async def voice_stt_configure(body: VoiceSTTConfig):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().configure_stt(body.language, body.model)

@router.post("/voice/transcribe")
async def voice_transcribe(body: VoiceTranscribe):
    from dash_backend.services.voice_engine import get_voice_engine
    return await get_voice_engine().transcribe(text_hint=body.text_hint)

@router.post("/voice/tts/configure")
async def voice_tts_configure(body: VoiceTTSConfig):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().configure_tts(body.voice, body.rate, body.pitch)

@router.post("/voice/synthesize")
async def voice_synthesize(body: VoiceSynthesize):
    from dash_backend.services.voice_engine import get_voice_engine
    return await get_voice_engine().synthesize(body.text, body.voice)

@router.post("/voice/command")
async def voice_command(body: VoiceCommandParse):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().parse_command(body.text)

@router.get("/voice/commands")
async def voice_commands(limit: int = 50):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().get_command_history(limit)

@router.post("/voice/memo")
async def voice_memo(body: VoiceMemoCreate):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().create_memo(body.text, body.duration, body.language, body.tags)

@router.get("/voice/memos")
async def voice_memos(language: str = None, limit: int = 50):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().get_memos(language, limit)

@router.delete("/voice/memos/{memo_id}")
async def voice_memo_delete(memo_id: str):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().delete_memo(memo_id)

@router.post("/voice/listening")
async def voice_listening(enabled: bool = True):
    from dash_backend.services.voice_engine import get_voice_engine
    return get_voice_engine().set_continuous_listening(enabled)


# ═════════════════════════════════════════════════════════════════════════════
# BROWSER AUTOMATION
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/browser/stats")
async def browser_stats():
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().get_stats()

@router.post("/browser/tabs/open")
async def browser_tab_open(body: TabOpen):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().open_tab(body.url, body.title, body.active)

@router.get("/browser/tabs")
async def browser_tabs():
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().get_tabs()

@router.post("/browser/tabs/{tab_id}/close")
async def browser_tab_close(tab_id: str):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().close_tab(tab_id)

@router.post("/browser/tabs/{tab_id}/focus")
async def browser_tab_focus(tab_id: str):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().focus_tab(tab_id)

@router.post("/browser/tabs/{tab_id}/pin")
async def browser_tab_pin(tab_id: str, pinned: bool = True):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().pin_tab(tab_id, pinned)

@router.post("/browser/tabs/group")
async def browser_tabs_group(tab_ids: list[str], group_name: str):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().group_tabs(tab_ids, group_name)

@router.get("/browser/tabs/search")
async def browser_tabs_search(query: str):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().search_tabs(query)

@router.post("/browser/screenshot")
async def browser_screenshot(tab_id: str = None, full_page: bool = False):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().take_screenshot(tab_id, full_page)

@router.get("/browser/screenshots")
async def browser_screenshots(limit: int = 20):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().get_screenshots(limit)

@router.post("/browser/summarize")
async def browser_summarize(url: str, content: str = ""):
    from dash_backend.services.browser_automation import get_browser_service
    return await get_browser_service().summarize_page(url, content)

@router.post("/browser/bookmarks")
async def browser_bookmark_add(body: BookmarkCreate):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().add_bookmark(body.url, body.title, body.folder, body.tags)

@router.get("/browser/bookmarks")
async def browser_bookmarks(folder: str = None, tag: str = None):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().get_bookmarks(folder, tag)

@router.get("/browser/bookmarks/search")
async def browser_bookmarks_search(query: str):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().search_bookmarks(query)

@router.delete("/browser/bookmarks/{bookmark_id}")
async def browser_bookmark_delete(bookmark_id: str):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().delete_bookmark(bookmark_id)

@router.get("/browser/bookmarks/folders")
async def browser_bookmark_folders():
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().get_folders()

@router.post("/browser/history")
async def browser_history_add(url: str, title: str, duration: float = 0, referrer: str = ""):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().add_history(url, title, duration, referrer)

@router.get("/browser/history")
async def browser_history(limit: int = 100):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().get_history(limit)

@router.delete("/browser/history")
async def browser_history_clear(days: int = 0):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().clear_history(days)

@router.get("/browser/history/search")
async def browser_history_search(query: str, limit: int = 50):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().search_history(query, limit)

@router.post("/browser/reading-list")
async def browser_reading_list_add(body: ReadingListAdd):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().add_to_reading_list(body.url, body.title, body.priority)

@router.get("/browser/reading-list")
async def browser_reading_list(status: str = None):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().get_reading_list(status)

@router.patch("/browser/reading-list/{item_id}")
async def browser_reading_list_update(item_id: str, status: str):
    from dash_backend.services.browser_automation import get_browser_service
    return get_browser_service().update_reading_list_item(item_id, status)


# ═════════════════════════════════════════════════════════════════════════════
# PUSH NOTIFICATIONS
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/notifications/push/stats")
async def push_notif_stats():
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_stats()

@router.post("/notifications/push/send")
async def push_notif_send(body: NotifSend):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().send(
        body.title, body.body, body.channel, body.priority,
        body.data, body.image_url, body.action_url, body.scheduled_at,
    )

@router.get("/notifications/push")
async def push_notif_list(channel: str = None, status: str = None, limit: int = 50):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_notifications(channel, status, limit)

@router.post("/notifications/push/{notif_id}/read")
async def push_notif_read(notif_id: str):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().mark_read(notif_id)

@router.post("/notifications/push/read-all")
async def push_notif_read_all():
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().mark_all_read()

@router.delete("/notifications/push")
async def push_notif_clear(channel: str = None):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().clear(channel)

@router.get("/notifications/push/unread")
async def push_notif_unread():
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_unread_count()

# Channels
@router.post("/notifications/channels")
async def push_channel_create(body: NotifChannelCreate):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().create_channel(body.name, body.type, body.config)

@router.get("/notifications/channels")
async def push_channels():
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_channels()

@router.patch("/notifications/channels/{channel_id}")
async def push_channel_update(channel_id: str, enabled: bool = True):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().update_channel(channel_id, enabled=enabled)

@router.delete("/notifications/channels/{channel_id}")
async def push_channel_delete(channel_id: str):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().delete_channel(channel_id)

# Templates
@router.post("/notifications/templates")
async def push_template_create(body: NotifTemplateCreate):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().create_template(
        body.name, body.title_template, body.body_template, body.channel, body.schedule
    )

@router.get("/notifications/templates")
async def push_templates():
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_templates()

@router.post("/notifications/templates/{template_id}/send")
async def push_template_send(template_id: str, variables: dict = {}):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().send_from_template(template_id, variables)

@router.delete("/notifications/templates/{template_id}")
async def push_template_delete(template_id: str):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().delete_template(template_id)

# Device registration
@router.post("/notifications/devices")
async def push_device_register(body: DeviceRegister):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().register_device(body.device_id, body.platform, body.token)

@router.delete("/notifications/devices/{device_id}")
async def push_device_unregister(device_id: str):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().unregister_device(device_id)

@router.get("/notifications/devices")
async def push_devices():
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_subscribers()

# Preferences
@router.post("/notifications/preferences/{user_id}")
async def push_prefs_set(user_id: str, body: NotifPrefs):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().set_preferences(user_id, body.model_dump())

@router.get("/notifications/preferences/{user_id}")
async def push_prefs_get(user_id: str):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_preferences(user_id)

@router.post("/notifications/quiet-hours/{user_id}")
async def push_quiet_hours(user_id: str, body: QuietHours):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().set_quiet_hours(user_id, body.start_hour, body.end_hour)

@router.get("/notifications/quiet-hours/{user_id}")
async def push_quiet_hours_get(user_id: str):
    from dash_backend.services.notifications_push import get_notification_service
    return get_notification_service().get_quiet_hours(user_id)
