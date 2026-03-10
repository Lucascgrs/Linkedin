"""
SessionManager — creates and loads LinkedIn Playwright sessions.
Note : le chargement de session est maintenant géré directement par StealthBrowser
via storage_state dans new_context (cookies + localStorage).
"""
import os


class SessionManager:
    """Manages LinkedIn browser sessions saved to JSON."""

    SESSION_FILE = "linkedin_session.json"

    @staticmethod
    async def create_session(output_path: str = SESSION_FILE) -> None:
        """
        Open a browser, wait for manual login, then save the session.
        Lance plutôt Sessions.py directement pour créer une session.
        """
        import importlib, sys
        # Sessions.py est à la racine du projet Linkedin
        import os as _os
        root = _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)
        sessions_mod = importlib.import_module("Sessions")
        await sessions_mod.create_session()

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
        print(f"✓ Session LinkedIn active ({session_path})")
