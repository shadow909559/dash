"""Form Automation - Auto login, form filling, and button clicking for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FormAutomation:
    def __init__(self):
        self._credentials: Dict[str, Dict[str, str]] = {}
        self._form_profiles: Dict[str, Dict[str, str]] = {}
    
    async def fill_form(self, page, data: Dict[str, str]) -> Dict[str, Any]:
        filled = 0
        errors = []
        for selector, value in data.items():
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.fill(value)
                    filled += 1
                else:
                    errors.append(f"Selector not found: {selector}")
            except Exception as exc:
                errors.append(f"Failed to fill {selector}: {exc}")
        return {"filled": filled, "errors": errors}
    
    async def auto_fill(self, page, profile_name: str = "default") -> Dict[str, Any]:
        profile = self._form_profiles.get(profile_name, {})
        if not profile:
            return {"filled": 0, "error": f"Profile '{profile_name}' not found"}
        return await self.fill_form(page, profile)
    
    async def auto_login(self, page, url: str, site_key: str = "") -> bool:
        if not site_key:
            from urllib.parse import urlparse
            site_key = urlparse(url).netloc
        creds = self._credentials.get(site_key)
        if not creds:
            return False
        try:
            username_sel = 'input[type="email"], input[type="text"][name*="user"], input[name*="login"]'
            password_sel = 'input[type="password"]'
            username_el = await page.query_selector(username_sel)
            password_el = await page.query_selector(password_sel)
            if username_el and password_el:
                await username_el.fill(creds.get("username", ""))
                await password_el.fill(creds.get("password", ""))
                submit_sel = 'button[type="submit"], input[type="submit"]'
                submit = await page.query_selector(submit_sel)
                if submit:
                    await submit.click()
                return True
            return False
        except Exception:
            return False
    
    async def click_button(self, page, selector: str) -> bool:
        try:
            button = await page.query_selector(selector)
            if button:
                await button.click()
                return True
            return False
        except Exception:
            return False
    
    async def click_link(self, page, text: str) -> bool:
        try:
            link = await page.query_selector(f'a:has-text("{text}")')
            if link:
                await link.click()
                return True
            return False
        except Exception:
            return False
    
    def save_credential(self, site: str, username: str, password: str) -> None:
        self._credentials[site] = {"username": username, "password": password}
    
    def save_profile(self, name: str, fields: Dict[str, str]) -> None:
        self._form_profiles[name] = fields


# Global singleton
_form_automation: Optional[FormAutomation] = None


def get_form_automation() -> FormAutomation:
    global _form_automation
    if _form_automation is None:
        _form_automation = FormAutomation()
    return _form_automation
