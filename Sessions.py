#!/usr/bin/env python3
"""
Sessions.py — Création et gestion des sessions LinkedIn.

Deux comptes sont supportés :
  1. Compte PRINCIPAL  → linkedin_session_main.json
     Utilisé pour les actions sensibles : envoi de messages, candidatures,
     ajout de contacts. Ce compte NE DOIT PAS être banni.

  2. Compte SCRAPER    → linkedin_session_scraper.json
     Compte "burner" dédié au scraping (peut être banni sans conséquence).
     Utilisé pour les recherches, l'exploration d'entreprises, les profils, etc.

Lance ce script UNE SEULE FOIS par compte, connecte-toi manuellement
dans le navigateur qui s'ouvre, et ta session sera sauvegardée.
"""
import asyncio
from linkedin.utils.session import SessionManager
from linkedin.utils.stealth_browser import SESSION_FILES


def _print_banner() -> None:
    print("\n" + "═" * 55)
    print("   🔐  Gestionnaire de sessions LinkedIn")
    print("═" * 55)
    for key, path in SESSION_FILES.items():
        import os
        status = "✅ existe" if os.path.exists(path) else "❌ manquant"
        label = "PRINCIPAL (messages/candidatures)" if key == "main" else "SCRAPER  (burner — scraping)"
        print(f"  [{key:7s}]  {label}")
        print(f"            → {path}  ({status})")
    print("═" * 55)


async def main() -> None:
    _print_banner()
    print("\nQuel compte veux-tu configurer ?")
    print("  1  →  Compte PRINCIPAL  (main)")
    print("  2  →  Compte SCRAPER    (scraper / burner)")
    print("  q  →  Quitter\n")

    choice = input("Ton choix [1/2/q] : ").strip().lower()

    if choice in ("1", "main"):
        await SessionManager.create_session(account="main")
    elif choice in ("2", "scraper"):
        await SessionManager.create_session(account="scraper")
    elif choice in ("q", "quit", "exit"):
        print("Annulé.")
    else:
        print(f"Choix invalide : '{choice}'")


if __name__ == "__main__":
    asyncio.run(main())

