"""
StealthBrowser — BrowserManager avec protection anti-détection bot.
Remplace 'BrowserManager' de linkedin-scraper dans tout le projet.
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


class StealthBrowser:
    """
    Contexte async qui lance Chromium en mode furtif.
    S'utilise exactement comme BrowserManager :
        async with StealthBrowser(headless=False) as browser:
            await SessionManager.load(browser)
            ...
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()

        # User-agent réaliste d'un vrai Chrome Windows
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        self.context = await self._browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1366, "height": 768},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            java_script_enabled=True,
            accept_downloads=False,
        )

        self.page = await self.context.new_page()

        # Applique playwright-stealth (cache navigator.webdriver etc.)
        await stealth_async(self.page)

        return self

    async def __aexit__(self, *args):
        await self._browser.close()
        await self._playwright.stop()

    # ---- Compatibilité avec SessionManager (load_session / save_session) ----

    async def save_session(self, path: str) -> None:
        """Sauvegarde cookies + storage dans un fichier JSON."""
        storage = await self.context.storage_state()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(storage, f)
        print(f"✅ Session sauvegardée dans {path}")

    async def load_session(self, path: str) -> None:
        """Recharge une session depuis un fichier JSON."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Session introuvable : {path}")
        with open(path, encoding="utf-8") as f:
            storage = json.load(f)
        await self.context.add_cookies(storage.get("cookies", []))
        print(f"✓ Session chargée depuis {path}")
