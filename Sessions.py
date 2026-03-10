#!/usr/bin/env python3
"""
ÉTAPE 1 : Créer ta session LinkedIn.
Lance ce script UNE SEULE FOIS, connecte-toi manuellement dans le navigateur,
et ta session sera sauvegardée dans linkedin_session.json
"""
import asyncio
from linkedin.utils.session import SessionManager


if __name__ == "__main__":
    asyncio.run(SessionManager.create_session())