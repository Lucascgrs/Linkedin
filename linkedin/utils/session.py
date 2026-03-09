"""
SessionManager — creates and loads LinkedIn Playwright sessions.
"""
from linkedin_scraper import BrowserManager, wait_for_manual_login


class SessionManager:
    """Manages LinkedIn browser sessions saved to JSON."""

    SESSION_FILE = "linkedin_session.json"

    @staticmethod
    async def create_session(output_path: str = SESSION_FILE) -> None:
        """
        Open a browser, wait for manual login, then save the session.

        Args:
            output_path: Path where the session JSON will be saved.
        """
        print("=" * 50)
        print("  Création de la session LinkedIn")
        print("=" * 50)
        print("\n1. Un navigateur va s'ouvrir")
        print("2. Connecte-toi manuellement à LinkedIn")
        print("3. La session sera sauvegardée automatiquement\n")

        async with BrowserManager(headless=False) as browser:
            await browser.page.goto("https://www.linkedin.com/login")
            print("⏳ En attente de ta connexion (5 minutes max)...")
            await wait_for_manual_login(browser.page, timeout=300_000)
            await browser.save_session(output_path)
            print(f"\n✅ Session sauvegardée dans {output_path}")
            print("⚠️  Ne commite JAMAIS ce fichier sur Git !")

    @staticmethod
    async def load(browser: BrowserManager, session_path: str = SESSION_FILE) -> None:
        """
        Load a previously saved session into the given browser instance.

        Args:
            browser:      An active BrowserManager context.
            session_path: Path to the session JSON file.
        """
        await browser.load_session(session_path)
        print(f"✓ Session chargée depuis {session_path}")
