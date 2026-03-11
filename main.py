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
# Pipeline complet : recherche entreprises → posts + employés
# ============================================================

async def pipeline_entreprises(
    pays: str = "france",
    secteur: str = "",
    taille: list[str] | None = None,
    keywords: str = "",
    max_companies: int = 10,
    filtre_poste: str = "",
    max_personnes: int = 20,
    max_posts: int = 10,
):
    """
    Pipeline complet :
      1. Recherche et scrape les entreprises correspondant aux filtres.
      2. Pour chaque entreprise trouvée dans le JSON sauvegardé,
         scrape ses posts ET ses employés avec les filtres fournis.
      3. Sauvegarde tout dans output/.

    Args:
        pays:          Pays de l'entreprise (ex: "france").
        secteur:       Secteur d'activité (ex: "software", "finance").
        taille:        Tailles d'entreprise (ex: ["11-50", "51-200"]).
        keywords:      Mots-clés pour la recherche d'entreprises.
        max_companies: Nombre maximum d'entreprises à traiter.
        filtre_poste:  Filtre sur le titre de poste pour les employés (ex: "developer").
        max_personnes: Nombre maximum d'employés à scraper par entreprise.
        max_posts:     Nombre maximum de posts à scraper par entreprise.
    """
    async with BrowserManager(headless=False) as browser:
        await SessionManager.load(browser)

        # ── Étape 1 : Recherche + scrape des entreprises ────────────────
        print("\n═══ ÉTAPE 1 : Recherche des entreprises ═══")
        search = CompanySearch(browser.page)
        companies = await search.search_and_scrape(
            pays=pays,
            secteur=secteur,
            taille=taille or [],
            keywords=keywords,
            max_companies=max_companies,
        )
        ExportUtils.to_json_and_excel(companies, "output/pipeline_companies", "Entreprises")
        print(f"  → {len(companies)} entreprise(s) trouvée(s) et sauvegardées.")

        # ── Étape 2 : Scrape posts + employés pour chaque entreprise ────
        people_scraper = PeopleScraper(browser.page)
        posts_scraper  = PostsScraper(browser.page)

        all_people: list[dict] = []
        all_posts:  list[dict] = []

        for i, company in enumerate(companies, 1):
            company_url = company.get("linkedin_url", "")
            company_name = company.get("name", company_url)
            if not company_url:
                print(f"  [{i}/{len(companies)}] URL manquante, entreprise ignorée.")
                continue

            print(f"\n═══ ÉTAPE 2 [{i}/{len(companies)}] : {company_name} ═══")

            # -- Posts --
            print(f"  → Scrape des posts ({max_posts} max)...")
            try:
                posts = await posts_scraper.scrape(company_url, limit=max_posts)
                for post in posts:
                    post["_company_url"] = company_url
                    post["_company_name"] = company_name
                all_posts.extend(posts)
                print(f"     {len(posts)} post(s) récupéré(s).")
            except Exception as e:
                print(f"     ✗ Erreur posts : {e}")

            # -- Employés --
            print(f"  → Scrape des employés ({max_personnes} max, filtre: '{filtre_poste or 'aucun'}')...")
            try:
                people = await people_scraper.scrape_company_people(
                    company_url=company_url,
                    filtre_poste=filtre_poste,
                    max_personnes=max_personnes,
                )
                for person in people:
                    person["_company_url"] = company_url
                    person["_company_name"] = company_name
                all_people.extend(people)
                print(f"     {len(people)} employé(s) récupéré(s).")
            except Exception as e:
                print(f"     ✗ Erreur employés : {e}")

        # ── Étape 3 : Export global ──────────────────────────────────────
        print("\n═══ ÉTAPE 3 : Export des résultats ═══")
        if all_posts:
            ExportUtils.to_json_and_excel(all_posts, "output/pipeline_posts", "Posts")
        if all_people:
            ExportUtils.to_json_and_excel(all_people, "output/pipeline_people", "Employés")

        print(f"\n✓ Pipeline terminé : {len(companies)} entreprise(s), "
              f"{len(all_posts)} post(s), {len(all_people)} employé(s).")


# ============================================================
# Entry point — uncomment the example you want to run
# ============================================================

if __name__ == "__main__":
    # --- Example 1: Search companies ---
    #asyncio.run(exemple_recherche_entreprises())

    # --- Example 2: Search jobs ---
    #asyncio.run(exemple_recherche_emplois())

    # --- Example 4: Scrape employees ---
    # asyncio.run(exemple_employes("https://www.linkedin.com/company/datasulting/"))

    # --- Example 5: Scrape posts ---
    # asyncio.run(exemple_posts("https://www.linkedin.com/company/Datasulting/"))

    # --- Example 7: Send a message ---
    # asyncio.run(exemple_message(
    #     profile_url="https://www.linkedin.com/in/luc-maurette/",
    #     message="Bonjour, je vous contacte car...",
    # ))

    # --- Example 8: Bulk messages ---
    # asyncio.run(exemple_messages_bulk([
    #     {
    #         "profile_url": "https://www.linkedin.com/in/PROFILE_SLUG/",
    #         "message": "Bonjour, je vous contacte car...",
    #     },
    # ]))

    # --- Pipeline complet : recherche entreprises → posts + employés ---
    asyncio.run(pipeline_entreprises(
        pays="france",
        secteur="conseil",
        taille=["11-50", "51-200"],
        keywords="",
        max_companies=10,
        filtre_poste="",        # ex: "developer", "manager", ...
        max_personnes=10,
        max_posts=5,
    ))

