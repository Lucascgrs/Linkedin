#!/usr/bin/env python3
"""
ÉTAPE 1 : Créer ta session LinkedIn.
Lance ce script UNE SEULE FOIS, connecte-toi manuellement dans le navigateur,
et ta session sera sauvegardée dans linkedin_session.json
"""
import asyncio
from linkedin_scraper import BrowserManager, wait_for_manual_login


async def create_session():
    print("=" * 50)
    print("  Création de la session LinkedIn")
    print("=" * 50)
    print("\n1. Un navigateur va s'ouvrir")
    print("2. Connecte-toi manuellement à LinkedIn")
    print("3. La session sera sauvegardée automatiquement\n")

    async with BrowserManager(headless=False) as browser:
        await browser.page.goto("https://www.linkedin.com/login")

        print("⏳ En attente de ta connexion (5 minutes max)...")
        await wait_for_manual_login(browser.page, timeout=300000)

        await browser.save_session("linkedin_session.json")
        print("\n✅ Session sauvegardée dans linkedin_session.json")
        print("⚠️  Ne commite JAMAIS ce fichier sur Git !")


if __name__ == "__main__":
    asyncio.run(create_session())