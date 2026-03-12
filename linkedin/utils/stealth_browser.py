"""
StealthBrowser — BrowserManager avec protection anti-détection bot.
Remplace 'BrowserManager' de linkedin-scraper dans tout le projet.

Comptes disponibles :
  - "main"    → linkedin_session_main.json    (compte principal : messages, candidatures)
  - "scraper" → linkedin_session_scraper.json (compte burner : scraping uniquement)

Rétrocompatibilité : si session_path est fourni explicitement, il est prioritaire.
"""
import json
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Fichier de session par défaut (rétrocompatibilité)
SESSION_FILE = "linkedin_session.json"

# Fichiers de session par compte
SESSION_FILES = {
    "main":    "linkedin_session_main.json",
    "scraper": "linkedin_session_scraper.json",
}


class StealthBrowser:
    """
    Contexte async qui lance Chromium en mode furtif.
    S'utilise exactement comme BrowserManager :
        async with StealthBrowser(headless=False, account="scraper") as browser:
            await SessionManager.load(browser)
            ...

    Paramètres :
        headless     : True pour mode sans tête.
        session_path : Chemin explicite vers le fichier de session JSON.
                       Si fourni, prioritaire sur account.
        account      : "main" ou "scraper". Détermine automatiquement session_path
                       si session_path n'est pas fourni explicitement.
                       Défaut : "main" (rétrocompatibilité).
    """

    def __init__(
        self,
        headless: bool = False,
        session_path: str = "",
        account: str = "main",
    ):
        self.headless = headless
        # Résolution du chemin de session :
        # 1. session_path explicite → utilisé tel quel
        # 2. account connu          → SESSION_FILES[account]
        # 3. Fallback               → SESSION_FILE (linkedin_session.json)
        if session_path:
            self.session_path = session_path
        elif account in SESSION_FILES:
            self.session_path = SESSION_FILES[account]
        else:
            self.session_path = SESSION_FILE
        self.account = account
        self._playwright = None
        self._browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()

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

        # Charge la session directement dans new_context si le fichier existe.
        # C'est la méthode officielle Playwright : cookies + localStorage restaurés d'un coup.
        storage_state = self.session_path if os.path.exists(self.session_path) else None

        self.context = await self._browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1366, "height": 768},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            java_script_enabled=True,
            accept_downloads=False,
            storage_state=storage_state,
        )


        self.page = await self.context.new_page()

        # Applique playwright-stealth (cache navigator.webdriver etc.)
        await Stealth().apply_stealth_async(self.page)

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

    async def load_session(self, path: str) -> None:
        """
        Recharge une session depuis un fichier JSON (cookies uniquement).
        Méthode de compatibilité — préfère passer session_path au constructeur
        pour une restauration complète (cookies + localStorage).
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Session introuvable : {path}")
        with open(path, encoding="utf-8") as f:
            storage = json.load(f)
        await self.context.add_cookies(storage.get("cookies", []))
