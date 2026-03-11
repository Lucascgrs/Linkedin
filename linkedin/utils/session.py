"""
SessionManager — creates and loads LinkedIn Playwright sessions.
Note : le chargement de session est maintenant géré directement par StealthBrowser
via storage_state dans new_context (cookies + localStorage).
"""
import asyncio
import os


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

    SESSION_FILE = "linkedin_session.json"

    @staticmethod
    async def create_session(output_path: str = SESSION_FILE) -> None:
        """
        Ouvre un navigateur, attend la connexion manuelle, puis sauvegarde la session.

        Args:
            output_path: Chemin du fichier JSON de session (défaut: linkedin_session.json).
        """
        from linkedin.utils.stealth_browser import StealthBrowser

        print("=" * 50)
        print("  Création de la session LinkedIn")
        print("=" * 50)
        print("\n1. Un navigateur va s'ouvrir")
        print("2. Connecte-toi manuellement à LinkedIn")
        print("3. La session sera sauvegardée automatiquement\n")

        # Démarre sans session existante
        async with StealthBrowser(headless=False, session_path="") as browser:
            await browser.page.goto("https://www.linkedin.com/login")
            print("⏳ En attente de ta connexion (5 minutes max)...")
            await _wait_for_manual_login(browser.page, timeout=300_000)
            await browser.save_session(output_path)
            print(f"\n✅ Session sauvegardée dans {output_path}")
            print("⚠️  Ne commite JAMAIS ce fichier sur Git !")

    @staticmethod
    async def load(browser, session_path: str = SESSION_FILE) -> None:
        """
        Vérifie que la session a bien été chargée par StealthBrowser.
        Le chargement réel se fait dans StealthBrowser.__aenter__ via storage_state.

        Args:
            browser:      An active StealthBrowser context.
            session_path: Path to the session JSON file (for logging only).
        """
        if not os.path.exists(session_path):
            raise FileNotFoundError(
                f"Session introuvable : {session_path}\n"
                f"Lance d'abord : python Sessions.py"
            )
        # La session est déjà chargée par StealthBrowser via storage_state.
        # On navigue vers le feed pour vérifier que la session est active.
        await browser.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        current_url = browser.page.url
        if "/login" in current_url or "/checkpoint" in current_url:
            raise RuntimeError(
                "Session expirée ou invalide. Relance : python Sessions.py"
            )
