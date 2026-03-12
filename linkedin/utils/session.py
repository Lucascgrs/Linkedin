"""
SessionManager — creates and loads LinkedIn Playwright sessions.
Note : le chargement de session est maintenant géré directement par StealthBrowser
via storage_state dans new_context (cookies + localStorage).

Deux comptes supportés :
  - "main"    → linkedin_session_main.json    (messages, candidatures)
  - "scraper" → linkedin_session_scraper.json (scraping, peut être banni)
"""
import asyncio
import os

from linkedin.utils.stealth_browser import SESSION_FILES, SESSION_FILE as _DEFAULT_SESSION_FILE


async def _wait_for_manual_login(page, timeout: int = 300_000) -> None:
    """Attend que l'utilisateur soit connecté (URL contient /feed, /in/ ou /jobs)."""
    deadline = asyncio.get_running_loop().time() + timeout / 1000
    while True:
        url = page.url
        if "linkedin.com/feed" in url or "linkedin.com/in/" in url or "linkedin.com/jobs" in url:
            return
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError("Délai de connexion dépassé")
        await asyncio.sleep(2)


class SessionManager:
    """Manages LinkedIn browser sessions saved to JSON."""

    # Rétrocompatibilité
    SESSION_FILE = _DEFAULT_SESSION_FILE

    @staticmethod
    async def create_session(output_path: str = "", account: str = "main") -> None:
        """
        Ouvre un navigateur, attend la connexion manuelle, puis sauvegarde la session.

        Args:
            output_path: Chemin du fichier JSON de session.
                         Si vide, déterminé automatiquement par account.
            account:     "main" ou "scraper". Ignoré si output_path est fourni.
        """
        from linkedin.utils.stealth_browser import StealthBrowser

        if not output_path:
            output_path = SESSION_FILES.get(account, _DEFAULT_SESSION_FILE)

        label = {
            "main":    "compte PRINCIPAL (messages / candidatures)",
            "scraper": "compte SCRAPER (burner — scraping uniquement)",
        }.get(account, f"compte '{account}'")

        print("=" * 55)
        print(f"  Création de la session LinkedIn — {label}")
        print("=" * 55)
        print("\n1. Un navigateur va s'ouvrir")
        print("2. Connecte-toi manuellement à LinkedIn")
        print(f"3. La session sera sauvegardée dans : {output_path}\n")

        # Démarre sans session existante
        async with StealthBrowser(headless=False, session_path="") as browser:
            await browser.page.goto("https://www.linkedin.com/login")
            print("⏳ En attente de ta connexion (5 minutes max)...")
            await _wait_for_manual_login(browser.page, timeout=300_000)
            await browser.save_session(output_path)
            print(f"\n✅ Session sauvegardée dans {output_path}")
            print("⚠️  Ne commite JAMAIS ce fichier sur Git !")

    @staticmethod
    async def load(browser, session_path: str = "", account: str = "") -> None:
        """
        Vérifie que la session a bien été chargée par StealthBrowser.
        Le chargement réel se fait dans StealthBrowser.__aenter__ via storage_state.

        Args:
            browser:      An active StealthBrowser context.
            session_path: Path to the session JSON file (for logging only).
                          Si vide, utilise browser.session_path.
            account:      Ignoré (conservé pour rétrocompatibilité).
        """
        effective_path = session_path or browser.session_path
        if not os.path.exists(effective_path):
            raise FileNotFoundError(
                f"Session introuvable : {effective_path}\n"
                f"Lance d'abord : python Sessions.py"
            )
        # La session est déjà chargée par StealthBrowser via storage_state.
        # On navigue vers le feed pour vérifier que la session est active.
        await browser.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        current_url = browser.page.url
        if "/login" in current_url or "/checkpoint" in current_url:
            raise RuntimeError(
                f"Session expirée ou invalide ({effective_path}). "
                f"Relance : python Sessions.py"
            )
        print(f"✅ Session chargée : {effective_path} (compte: {browser.account})")
