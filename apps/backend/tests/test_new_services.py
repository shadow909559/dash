# -*- coding: utf-8 -*-
"""Tests for new services: OAuth, Integrations, Voice Engine, Browser Automation, Push Notifications."""

import pytest
from dash_backend.services.oauth_social import get_oauth_service
from dash_backend.services.integrations import get_integration_service
from dash_backend.services.voice_engine import get_voice_engine
from dash_backend.services.browser_automation import get_browser_service
from dash_backend.services.notifications_push import get_notification_service


# ═════════════════════════════════════════════════════════════════════════════
# OAuth Service Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestOAuthService:

    def setup_method(self):
        self.svc = get_oauth_service()

    def test_configure_provider(self):
        result = self.svc.configure_provider("google", "client_id", "client_secret", "http://localhost")
        assert result["status"] == "configured"
        assert result["provider"] == "google"

    def test_configure_invalid_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            self.svc.configure_provider("invalid", "id", "secret", "uri")

    def test_get_authorize_url(self):
        self.svc.configure_provider("github", "gh_id", "gh_secret", "http://localhost/callback")
        result = self.svc.get_authorize_url("github")
        assert "authorization_url" in result
        assert "state" in result
        assert result["provider"] == "github"

    def test_get_authorize_url_unconfigured(self):
        with pytest.raises(ValueError, match="not configured"):
            self.svc.get_authorize_url("twitter")

    def test_link_account(self):
        result = self.svc.link_account("user1", "google", {
            "provider_user_id": "g_123",
            "email": "test@gmail.com",
            "name": "Test User",
        })
        assert result["status"] == "linked"
        assert result["provider"] == "google"

    def test_get_linked_accounts(self):
        self.svc.link_account("user1", "google", {
            "provider_user_id": "g_123", "email": "g@test.com", "name": "G User"
        })
        self.svc.link_account("user1", "github", {
            "provider_user_id": "gh_456", "email": "gh@test.com", "name": "GH User"
        })
        accounts = self.svc.get_linked_accounts("user1")
        assert len(accounts) == 2
        assert accounts[0]["provider"] == "google"
        assert accounts[1]["provider"] == "github"

    def test_unlink_account(self):
        self.svc.link_account("unlink_user", "google", {
            "provider_user_id": "g_999", "email": "g@test.com", "name": "G"
        })
        result = self.svc.unlink_account("unlink_user", "google")
        assert result["status"] == "unlinked"
        assert len(self.svc.get_linked_accounts("unlink_user")) == 0

    def test_unlink_nonexistent(self):
        result = self.svc.unlink_account("nonexistent_user_xyz", "google")
        assert result["status"] == "not_found"

    def test_get_provider_info(self):
        result = self.svc.get_provider_info("google")
        assert result["provider"] == "google"
        assert "authorize_url" in result
        assert "scopes" in result

    def test_get_configured_providers(self):
        self.svc.configure_provider("google", "id", "secret", "uri")
        providers = self.svc.get_configured_providers()
        assert len(providers) >= 1
        assert providers[0]["provider"] == "google"


# ═════════════════════════════════════════════════════════════════════════════
# Integration Service Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestIntegrationService:

    def setup_method(self):
        self.svc = get_integration_service()

    def test_configure(self):
        result = self.svc.configure("slack", api_key="xoxb-test")
        assert result["status"] == "configured"

    def test_configure_unsupported(self):
        with pytest.raises(ValueError, match="Unsupported"):
            self.svc.configure("unsupported_service")

    def test_send_message(self):
        self.svc.configure("telegram", bot_token="test_token")
        result = self.svc.send_message("telegram", "#general", "Hello!")
        assert result["status"] == "sent"
        assert result["service"] == "telegram"

    def test_send_message_unconfigured(self):
        with pytest.raises(ValueError, match="not configured"):
            self.svc.send_message("discord", "#general", "test")

    def test_receive_message(self):
        result = self.svc.receive_message("slack", "#general", "Hi there", "user1")
        assert result["status"] == "received"

    def test_get_messages(self):
        self.svc.send_message("slack", "#msg_test_ch", "msg1")
        self.svc.receive_message("slack", "#msg_test_ch", "msg2", "user1")
        msgs = self.svc.get_messages("slack", "#msg_test_ch")
        assert len(msgs) == 2

    def test_create_webhook(self):
        result = self.svc.create_webhook("github", "https://example.com/webhook", ["push", "pull_request"])
        assert result["status"] == "created"
        assert result["webhook_id"].startswith("wh_")

    def test_get_webhooks(self):
        self.svc.create_webhook("notion", "http://url1", ["push"])
        self.svc.create_webhook("slack", "http://url2", ["message"])
        whs = self.svc.get_webhooks("notion")
        assert len(whs) >= 1

    def test_delete_webhook(self):
        result = self.svc.create_webhook("github", "http://url", ["push"])
        del_result = self.svc.delete_webhook(result["webhook_id"])
        assert del_result["status"] == "deleted"

    def test_get_integrations_status(self):
        self.svc.configure("slack", api_key="key")
        status = self.svc.get_integrations_status()
        assert len(status) == len(self.svc.SUPPORTED_SERVICES)
        slack = next(s for s in status if s["service"] == "slack")
        assert slack["configured"] is True

    def test_get_events(self):
        self.svc.receive_message("slack", "#ch", "hello", "user1")
        events = self.svc.get_events()
        assert len(events) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# Voice Engine Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestVoiceEngine:

    def setup_method(self):
        self.svc = get_voice_engine()

    def test_configure_wake_word(self):
        result = self.svc.configure_wake_word(True, 0.8)
        assert result["enabled"] is True
        assert result["sensitivity"] == 0.8

    def test_detect_wake_word(self):
        result = self.svc.detect_wake_word("hey dash open browser")
        assert result["detected"] is True
        assert result["wake_word"] == "hey dash"
        assert "open browser" in result["command_text"]

    def test_detect_wake_word_not_found(self):
        result = self.svc.detect_wake_word("hello world")
        assert result["detected"] is False

    def test_configure_stt(self):
        result = self.svc.configure_stt("es", "large")
        assert result["language"] == "es"

    def test_configure_stt_invalid_lang(self):
        with pytest.raises(ValueError, match="Unsupported"):
            self.svc.configure_stt("xx")

    @pytest.mark.asyncio
    async def test_transcribe(self):
        result = await self.svc.transcribe(text_hint="hello world")
        assert result["text"] == "hello world"
        assert result["confidence"] > 0

    def test_configure_tts(self):
        result = self.svc.configure_tts("female", 1.5, 0.8)
        assert result["voice"] == "female"
        assert result["rate"] == 1.5

    @pytest.mark.asyncio
    async def test_synthesize(self):
        result = await self.svc.synthesize("Hello, world!")
        assert "audio_ref" in result
        assert result["text"] == "Hello, world!"

    def test_parse_command_open(self):
        result = self.svc.parse_command("open browser")
        assert result["recognized"] is True
        assert result["intent"] == "open_app"

    def test_parse_command_search(self):
        result = self.svc.parse_command("search weather today")
        assert result["recognized"] is True
        assert result["intent"] == "search"

    def test_parse_command_remember(self):
        result = self.svc.parse_command("remember buy milk")
        assert result["recognized"] is True
        assert result["intent"] == "create_memory"

    def test_parse_command_unrecognized(self):
        result = self.svc.parse_command("random gibberish")
        assert result["recognized"] is False

    def test_get_command_history(self):
        self.svc.parse_command("open terminal")
        self.svc.parse_command("search files")
        history = self.svc.get_command_history()
        assert len(history) >= 2

    def test_create_memo(self):
        result = self.svc.create_memo("Recorded thought", 15.0, "en", ["idea"])
        assert result["text"] == "Recorded thought"
        assert result["duration"] == 15.0

    def test_get_memos(self):
        self.svc.create_memo("Memo 1", 10.0, "en")
        self.svc.create_memo("Nota 1", 5.0, "es")
        all_memos = self.svc.get_memos()
        assert len(all_memos) >= 2
        es_memos = self.svc.get_memos(language="es")
        assert len(es_memos) >= 1

    def test_delete_memo(self):
        result = self.svc.create_memo("Delete me", 1.0)
        del_result = self.svc.delete_memo(result["id"])
        assert del_result["deleted"] is True

    def test_set_continuous_listening(self):
        result = self.svc.set_continuous_listening(True)
        assert result["continuous_listening"] is True

    def test_get_status(self):
        status = self.svc.get_status()
        assert "wake_word_enabled" in status
        assert "stt_language" in status
        assert "supported_languages" in status


# ═════════════════════════════════════════════════════════════════════════════
# Browser Automation Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestBrowserAutomation:

    def setup_method(self):
        self.svc = get_browser_service()

    def test_open_tab(self):
        result = self.svc.open_tab("https://example.com", "Example")
        assert result["url"] == "https://example.com"
        assert result["tab_id"].startswith("tab_")

    def test_close_tab(self):
        result = self.svc.open_tab("https://example.com")
        close = self.svc.close_tab(result["tab_id"])
        assert close["status"] == "closed"

    def test_get_tabs(self):
        self.svc.open_tab("https://taba.com", "A")
        self.svc.open_tab("https://tabb.com", "B")
        tabs = self.svc.get_tabs()
        assert len(tabs) >= 2

    def test_focus_tab(self):
        t1 = self.svc.open_tab("https://a.com")
        t2 = self.svc.open_tab("https://b.com")
        self.svc.focus_tab(t1["tab_id"])
        tabs = self.svc.get_tabs()
        focused = [t for t in tabs if t["is_active"]]
        assert len(focused) == 1

    def test_pin_tab(self):
        t = self.svc.open_tab("https://a.com")
        result = self.svc.pin_tab(t["tab_id"])
        assert result["status"] == "pinned"

    def test_group_tabs(self):
        t1 = self.svc.open_tab("https://a.com")
        t2 = self.svc.open_tab("https://b.com")
        result = self.svc.group_tabs([t1["tab_id"], t2["tab_id"]], "work")
        assert result["tab_count"] == 2

    def test_search_tabs(self):
        self.svc.open_tab("https://github.com", "GitHub")
        self.svc.open_tab("https://google.com", "Google")
        results = self.svc.search_tabs("github")
        assert len(results) == 1

    def test_screenshot(self):
        result = self.svc.take_screenshot(full_page=True)
        assert result["id"].startswith("ss_")
        assert result["full_page"] is True

    def test_get_screenshots(self):
        self.svc.take_screenshot()
        self.svc.take_screenshot()
        ss = self.svc.get_screenshots()
        assert len(ss) >= 2

    def test_add_bookmark(self):
        result = self.svc.add_bookmark("https://example.com", "Example", tags=["test"])
        assert result["url"] == "https://example.com"

    def test_get_bookmarks(self):
        self.svc.add_bookmark("https://bmwork.com", "A", folder="Work")
        self.svc.add_bookmark("https://bmpersonal.com", "B", folder="Personal")
        work = self.svc.get_bookmarks(folder="Work")
        assert len(work) >= 1

    def test_search_bookmarks(self):
        self.svc.add_bookmark("https://python.org", "Python Docs", tags=["python", "docs"])
        results = self.svc.search_bookmarks("python")
        assert len(results) == 1

    def test_delete_bookmark(self):
        bm = self.svc.add_bookmark("https://example.com", "Example")
        result = self.svc.delete_bookmark(bm["id"])
        assert result["status"] == "deleted"

    def test_add_history(self):
        result = self.svc.add_history("https://example.com", "Example", 30.0)
        assert result["status"] == "recorded"

    def test_get_history(self):
        self.svc.add_history("https://hista.com", "A")
        self.svc.add_history("https://histb.com", "B")
        history = self.svc.get_history()
        assert len(history) >= 2

    def test_search_history(self):
        self.svc.add_history("https://ghunique.com", "GitHub Unique")
        self.svc.add_history("https://google.com", "Google")
        results = self.svc.search_history("ghunique")
        assert len(results) == 1

    def test_clear_history(self):
        self.svc.add_history("https://unique-clear.com", "Unique Clear")
        result = self.svc.clear_history()
        assert result["cleared"] >= 1

    def test_reading_list(self):
        item = self.svc.add_to_reading_list("https://article.com", "Article", "high")
        assert item["status"] == "unread"
        self.svc.update_reading_list_item(item["id"], "read")
        rl = self.svc.get_reading_list(status="read")
        assert len(rl) == 1

    def test_get_stats(self):
        self.svc.open_tab("https://a.com")
        self.svc.add_bookmark("https://b.com", "B")
        stats = self.svc.get_stats()
        assert stats["open_tabs"] >= 1
        assert stats["bookmarks"] >= 1

    @pytest.mark.asyncio
    async def test_summarize_page(self):
        result = await self.svc.summarize_page("https://example.com", "Page content")
        assert "summary" in result
        assert result["url"] == "https://example.com"


# ═════════════════════════════════════════════════════════════════════════════
# Push Notification Service Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestPushNotificationService:

    def setup_method(self, method):
        self.svc = get_notification_service()
        # Deterministic sends: the service defers during its default quiet
        # hours (23:00-07:00 UTC), which made these tests fail when run at
        # night. Pin quiet hours off instead of depending on wall clock.
        self._orig_quiet = type(self.svc)._is_quiet_hours
        type(self.svc)._is_quiet_hours = lambda s: False

    def teardown_method(self, method):
        type(self.svc)._is_quiet_hours = self._orig_quiet

    def test_send_notification(self):
        result = self.svc.send("Hello", "World")
        assert result["status"] == "sent"
        assert result["id"].startswith("n_")

    def test_get_notifications(self):
        self.svc.send("Alert", "High priority", priority="high")
        self.svc.send("Info", "Low priority", priority="low")
        notifs = self.svc.get_notifications()
        assert len(notifs) >= 2

    def test_get_notifications_by_channel(self):
        self.svc.send("Alert", "Channel 1", channel="alerts")
        self.svc.send("Info", "Channel 2", channel="info")
        alerts = self.svc.get_notifications(channel="alerts")
        assert len(alerts) == 1

    def test_mark_read(self):
        notif = self.svc.send("Read me", "Content")
        result = self.svc.mark_read(notif["id"])
        assert result["status"] == "read"

    def test_mark_all_read(self):
        self.svc.send("n1", "body1")
        self.svc.send("n2", "body2")
        result = self.svc.mark_all_read()
        assert result["marked_read"] >= 2

    def test_clear_notifications(self):
        self.svc.send("n1", "b1")
        self.svc.send("n2", "b2")
        result = self.svc.clear()
        assert result["cleared"] >= 2

    def test_unread_count(self):
        self.svc.send("n1", "b1", channel="alertsch")
        self.svc.send("n2", "b2", channel="alertsch")
        self.svc.send("n3", "b3", channel="infoch")
        counts = self.svc.get_unread_count()
        assert counts["total"] >= 3
        assert counts["alertsch"] >= 2

    def test_create_channel(self):
        result = self.svc.create_channel("Slack Alerts", "webhook")
        assert result["type"] == "webhook"
        assert result["id"].startswith("ch_")

    def test_get_channels(self):
        self.svc.create_channel("Email", "email")
        self.svc.create_channel("SMS", "sms")
        channels = self.svc.get_channels()
        assert len(channels) >= 2

    def test_create_template(self):
        result = self.svc.create_template("Daily Report", "Report: {date}", "Summary for {date}")
        assert result["name"] == "Daily Report"

    def test_send_from_template(self):
        tpl = self.svc.create_template("Reminder", "{task} is due", "Complete {task}")
        result = self.svc.send_from_template(tpl["id"], {"task": "homework"})
        assert result["status"] == "sent"

    def test_register_device(self):
        result = self.svc.register_device("device_123", "android", "fcm_token")
        assert result["status"] == "registered"

    def test_unregister_device(self):
        self.svc.register_device("device_123", "android")
        result = self.svc.unregister_device("device_123")
        assert result["status"] == "unregistered"

    def test_get_subscribers(self):
        self.svc.register_device("d_sub_1", "android")
        self.svc.register_device("d_sub_2", "ios")
        subs = self.svc.get_subscribers()
        assert len(subs) >= 2

    def test_set_preferences(self):
        result = self.svc.set_preferences("user1", {"push": True, "email": False})
        assert result["status"] == "saved"

    def test_get_preferences(self):
        prefs = self.svc.get_preferences("pref_user_unique")
        assert "channels" in prefs
        assert "priority_filter" in prefs

    def test_set_quiet_hours(self):
        result = self.svc.set_quiet_hours("user1", 22, 7)
        assert "quiet_hours" in result

    def test_get_stats(self):
        self.svc.send("n1", "b1")
        self.svc.create_channel("Test", "push")
        stats = self.svc.get_stats()
        assert stats["total_notifications"] >= 1
        assert stats["channels"] >= 1
