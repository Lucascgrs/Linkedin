#!/usr/bin/env python3
"""
main.py — Usage examples for the linkedin package.

Each async function demonstrates one feature.
Run a specific example by calling it from the __main__ block.

Setup:
    1. Install dependencies:   pip install -r requirements.txt
    2. Install browser:        playwright install chromium
    3. Create your session:    python Sessions.py
    4. Run an example below.
"""
import asyncio

from linkedin.utils.stealth_browser import StealthBrowser as BrowserManager

from linkedin.utils.session import SessionManager
from linkedin.utils.export import ExportUtils
from linkedin.scrapers.company_scraper import CompanyScraper
from linkedin.scrapers.job_scraper import JobScraper
from linkedin.scrapers.people_scraper import PeopleScraper
from linkedin.scrapers.posts_scraper import PostsScraper
from linkedin.search.company_search import CompanySearch
from linkedin.search.job_search import JobSearch
from linkedin.actions.messenger import LinkedInMessenger


# ============================================================
# Exemple 1 : Rechercher des entreprises
# ============================================================

async def exemple_recherche_entreprises():
    """Search for companies and export results to JSON + Excel."""
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        search = CompanySearch(browser.page)
        results = await search.search_and_scrape(
            pays="france",
            secteur="software",
            taille=["11-50", "51-200"],
            keywords="data",
            max_companies=5,
        )
        ExportUtils.to_json_and_excel(results, "output/companies", "Entreprises")


# ============================================================
# Exemple 2 : Rechercher des offres d'emploi
# ============================================================

async def exemple_recherche_emplois():
    """Search for job offers and export results to JSON + Excel."""
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        search = JobSearch(browser.page)
        results = await search.search_and_scrape(
            keywords="data analyst",
            pays="france",
            date_publiee="mois",
            mode_travail=[],
            type_contrat=["cdi"],
            max_offres=1,
        )
        ExportUtils.to_json_and_excel(results, "output/jobs", "Offres")


# ============================================================
# Exemple 3 : Scraper une entreprise spécifique
# ============================================================

async def exemple_scrape_entreprise(company_url: str):
    """Scrape details for a single company and export to JSON + Excel.

    Args:
        company_url: LinkedIn company URL, e.g.
                     "https://www.linkedin.com/company/microsoft/"
    """
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        scraper = CompanyScraper(browser.page)
        result = await scraper.scrape(company_url)
        ExportUtils.to_json_and_excel([result], "output/company", "Entreprise")


# ============================================================
# Exemple 4 : Employés d'une entreprise
# ============================================================

async def exemple_employes(company_url: str):
    """Scrape employees from a company page and export results.

    Args:
        company_url: LinkedIn company URL, e.g.
                     "https://www.linkedin.com/company/COMPANY_SLUG/"
    """
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        scraper = PeopleScraper(browser.page)
        results = await scraper.scrape_company_people(
            company_url=company_url,
            filtre_poste="",
            max_personnes=20,
        )
        ExportUtils.to_json_and_excel(results, "output/people", "Employés")


# ============================================================
# Exemple 5 : Posts d'une entreprise
# ============================================================

async def exemple_posts(company_url: str):
    """Scrape recent posts from a company page and export results.

    Args:
        company_url: LinkedIn company URL, e.g.
                     "https://www.linkedin.com/company/COMPANY_SLUG/"
    """
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        scraper = PostsScraper(browser.page)
        results = await scraper.scrape(
            company_url=company_url,
            limit=10,
        )
        ExportUtils.to_json_and_excel(results, "output/posts", "Posts")


# ============================================================
# Exemple 6 : Scraper une offre d'emploi spécifique
# ============================================================

async def exemple_scrape_offre(job_url: str):
    """Scrape details for a single job offer.

    Args:
        job_url: LinkedIn job URL, e.g.
                 "https://www.linkedin.com/jobs/view/1234567890/"
    """
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        scraper = JobScraper(browser.page, browser.context)
        result = await scraper.scrape(job_url)
        ExportUtils.to_json_and_excel([result], "output/job", "Offre")


# ============================================================
# Exemple 7 : Envoyer un message
# ============================================================

async def exemple_message(profile_url: str, message: str):
    """Send a direct message to a LinkedIn profile.

    Args:
        profile_url: LinkedIn profile URL, e.g.
                     "https://www.linkedin.com/in/PROFILE_SLUG/"
        message:     Text of the message to send.
    """
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        messenger = LinkedInMessenger(browser.page)
        success = await messenger.send_message(
            profile_url=profile_url,
            message=message,
        )
        print("✅ Message envoyé" if success else "❌ Échec de l'envoi")


# ============================================================
# Exemple 8 : Envoi en masse
# ============================================================

async def exemple_messages_bulk(contacts: list[dict]):
    """Send messages to multiple profiles.

    Args:
        contacts: List of dicts with keys "profile_url" and "message".
                  Example:
                  [
                      {
                          "profile_url": "https://www.linkedin.com/in/SLUG/",
                          "message": "Bonjour, je vous contacte car..."
                      },
                  ]
    """
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        messenger = LinkedInMessenger(browser.page)
        results = await messenger.send_messages_bulk(
            contacts=contacts,
            delay_between=(5, 15),
            max_messages=10,
        )
        ExportUtils.to_json(results, "output/messages_results.json")


# ============================================================
# Exemple 9 (DIAGNOSTIC) : Sauvegarder le HTML d'une offre
# ============================================================

async def diagnostic_html_offre(job_url: str):
    """Sauvegarde le HTML brut d'une offre pour inspecter les vraies classes CSS LinkedIn.

    Usage :
        1. Lancer cette fonction avec l'URL d'une offre
        2. Ouvrir output/debug_job.html dans un navigateur ou éditeur
        3. Chercher les classes CSS autour du titre, de l'entreprise, etc.

    Args:
        job_url: URL LinkedIn de l'offre, ex. "https://www.linkedin.com/jobs/view/1234567890/"
    """
    import os
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)
        page = browser.page
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        import asyncio as _a
        await _a.sleep(5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await _a.sleep(2)
        html = await page.content()
        os.makedirs("output", exist_ok=True)
        with open("output/debug_job.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ HTML sauvegardé dans output/debug_job.html ({len(html)} chars)")


# ============================================================
# Entry point — uncomment the example you want to run
# ============================================================

if __name__ == "__main__":
    # --- Example 1: Search companies ---
    #asyncio.run(exemple_recherche_entreprises())

    # --- Example 2: Search jobs ---
    #asyncio.run(exemple_recherche_emplois())

    # --- Example 3: Scrape a single company ---
    # asyncio.run(exemple_scrape_entreprise(
    #     "https://www.linkedin.com/company/COMPANY_SLUG/"
    # ))

    # --- Example 4: Scrape employees ---
    asyncio.run(exemple_employes("https://www.linkedin.com/company/datasulting/"))

    # --- Example 5: Scrape posts ---
    # asyncio.run(exemple_posts(
    #     "https://www.linkedin.com/company/COMPANY_SLUG/"
    # ))

    # --- Example 6: Scrape a single job offer ---
    # asyncio.run(exemple_scrape_offre(
    #     "https://www.linkedin.com/jobs/view/JOB_ID/"
    # ))

    # --- Example 9: DIAGNOSTIC — Sauvegarder le HTML d'une offre pour inspecter les classes CSS ---
    # asyncio.run(diagnostic_html_offre(
    #     "https://www.linkedin.com/jobs/view/4379667856"
    # ))

    # --- Example 7: Send a message ---
    # asyncio.run(exemple_message(
    #     profile_url="https://www.linkedin.com/in/PROFILE_SLUG/",
    #     message="Bonjour, je vous contacte car...",
    # ))

    # --- Example 8: Bulk messages ---
    # asyncio.run(exemple_messages_bulk([
    #     {
    #         "profile_url": "https://www.linkedin.com/in/PROFILE_SLUG/",
    #         "message": "Bonjour, je vous contacte car...",
    #     },
    # ]))
