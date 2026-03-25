#!/usr/bin/env python3
"""
main.py — Usage examples for the linkedin package.

Each async function demonstrates one feature.
Run a specific example by calling it from the __main__ block.

Setup:
    1. Install dependencies:   pip install -r requirements.txt
    2. Install browser:        playwright install chromium
    3. Create your sessions:   python Sessions.py
         → choisir 1 (compte PRINCIPAL)  : linkedin_session_main.json
         → choisir 2 (compte SCRAPER)    : linkedin_session_scraper.json
    4. Run an example below.

Architecture dual-session :
    ┌─────────────────────────────────────────────────────────┐
    │  account="scraper"  →  linkedin_session_scraper.json    │
    │    Utilisé pour : recherche entreprises, scraping        │
    │    profils/posts/employés — peut être banni sans risque  │
    ├─────────────────────────────────────────────────────────┤
    │  account="main"     →  linkedin_session_main.json        │
    │    Utilisé pour : envoi de messages, candidatures,       │
    │    ajout de contacts — NE DOIT PAS être banni            │
    └─────────────────────────────────────────────────────────┘
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
from linkedin.actions.connection_manager import ConnectionManager
from linkedin.actions.easy_apply import EasyApply


# ============================================================
# Exemple 1 : Rechercher des entreprises  [compte SCRAPER]
# ============================================================

async def exemple_recherche_entreprises():
    """Search for companies and export results to JSON + Excel."""
    async with BrowserManager(headless=False, account="scraper") as browser:
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
# Exemple 2 : Rechercher des offres d'emploi  [compte SCRAPER]
# ============================================================

async def exemple_recherche_emplois():
    """Search for job offers and export results to JSON + Excel."""
    async with BrowserManager(headless=False, account="scraper") as browser:
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
# Exemple 4 : Employés d'une entreprise  [compte SCRAPER]
# ============================================================

async def exemple_employes(company_url: str):
    """Scrape employees from a company page and export results.

    Args:
        company_url: LinkedIn company URL, e.g.
                     "https://www.linkedin.com/company/COMPANY_SLUG/"
    """
    async with BrowserManager(headless=False, account="scraper") as browser:
        await SessionManager.load(browser)
        scraper = PeopleScraper(browser.page)
        results = await scraper.scrape_company_people(
            company_url=company_url,
            filtre_poste="",
            max_personnes=20,
        )
        ExportUtils.to_json_and_excel(results, "output/people", "Employés")


# ============================================================
# Exemple 5 : Posts d'une entreprise  [compte SCRAPER]
# ============================================================

async def exemple_posts(company_url: str):
    """Scrape recent posts from a company page and export results.

    Args:
        company_url: LinkedIn company URL, e.g.
                     "https://www.linkedin.com/company/COMPANY_SLUG/"
    """
    async with BrowserManager(headless=False, account="scraper") as browser:
        await SessionManager.load(browser)
        scraper = PostsScraper(browser.page)
        results = await scraper.scrape(
            company_url=company_url,
            limit=10,
        )
        ExportUtils.to_json_and_excel(results, "output/posts", "Posts")


# ============================================================
# Exemple 6 : Ajouter une personne en contact  [compte MAIN]
# ============================================================

async def exemple_ajouter_contact(
    profile_url: str,
    note: str = "",
):
    """
    Envoie une demande de connexion à une personne et met à jour
    le fichier Excel de suivi (output/connections.xlsx).

    Si la personne est déjà dans le fichier, son entrée est mise à jour
    (is_following_back, last_updated) sans remettre à zéro la date d'ajout.

    Args:
        profile_url : URL complète du profil LinkedIn.
                      Ex: "https://www.linkedin.com/in/john-doe/"
        note        : Message personnalisé optionnel (max 300 caractères).
                      Laisse vide pour envoyer sans note.
    """
    async with BrowserManager(headless=False, account="main") as browser:
        await SessionManager.load(browser)
        cm = ConnectionManager(browser.page)
        result = await cm.add_connection(profile_url=profile_url, note=note)
        print(f"\n  Résultat : {result}")


# ============================================================
# Exemple 6b : Ajout en masse  [compte MAIN]
# ============================================================

async def exemple_ajouter_contacts_bulk(
    profile_urls: list[str],
    note: str = "",
):
    """
    Envoie des demandes de connexion à plusieurs profils avec délai anti-ban.
    Le fichier output/connections.xlsx est mis à jour après chaque invitation.

    Args:
        profile_urls : Liste d'URLs de profils LinkedIn.
        note         : Message optionnel joint à toutes les invitations.
    """
    async with BrowserManager(headless=False, account="main") as browser:
        await SessionManager.load(browser)
        cm = ConnectionManager(browser.page)
        results = await cm.add_connections_bulk(
            profile_urls=profile_urls,
            note=note,
            delay_between=(10, 25),
            max_invitations=20,
        )
        print(f"\n  {len(results)} profil(s) traité(s).")


# ============================================================
# Exemple 7 : Envoyer un message  [compte MAIN]
# ============================================================

async def exemple_message(profile_url: str, message: str):
    """Send a direct message to a LinkedIn profile.

    Args:
        profile_url: LinkedIn profile URL, e.g.
                     "https://www.linkedin.com/in/PROFILE_SLUG/"
        message:     Text of the message to send.
    """
    async with BrowserManager(headless=False, account="main") as browser:
        await SessionManager.load(browser)
        messenger = LinkedInMessenger(browser.page)
        success = await messenger.send_message(
            profile_url=profile_url,
            message=message,
        )


# ============================================================
# Exemple 8 : Envoi en masse  [compte MAIN]
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
    async with BrowserManager(headless=False, account="main") as browser:
        await SessionManager.load(browser)
        messenger = LinkedInMessenger(browser.page)
        results = await messenger.send_messages_bulk(
            contacts=contacts,
            delay_between=(5, 15),
            max_messages=10,
        )
        ExportUtils.to_json(results, "output/messages_results.json")


# ============================================================
# Exemple 9 : Postuler sur une offre Candidature simplifiée  [compte MAIN]
# ============================================================

async def exemple_postuler(
    job_url: str,
    cv_path: str,
    cover_letter_path: str | None = None,
    phone: str = "",
    default_answers: dict | None = None,
):
    """
    Postule automatiquement sur une offre LinkedIn en Candidature simplifiée.

    Le résultat est sauvegardé dans output/applications.xlsx.

    Args:
        job_url:           URL complète de l'offre LinkedIn.
                           Ex: "https://www.linkedin.com/jobs/view/1234567890/"
        cv_path:           Chemin absolu vers le CV (PDF ou DOCX).
        cover_letter_path: Chemin vers la lettre de motivation (optionnel).
        phone:             Numéro de téléphone pour les champs du formulaire.
        default_answers:   Réponses automatiques aux questions du formulaire.
                           Ex: {"années d'expérience": "3", "salaire souhaité": "45000"}
    """
    async with BrowserManager(headless=False, account="main") as browser:
        await SessionManager.load(browser)
        ea = EasyApply(
            page=browser.page,
            cv_path=cv_path,
            cover_letter_path=cover_letter_path,
            phone=phone,
            default_answers=default_answers or {},
        )
        result = await ea.apply(job_url)
        print(f"\n  Résultat : {result['status']} — {result.get('title', '?')} @ {result.get('company', '?')}")


# ============================================================
# Exemple 9b : Postuler en masse (Candidatures simplifiées)  [compte MAIN]
# ============================================================

async def exemple_postuler_bulk(
    job_urls: list[str],
    cv_path: str,
    cover_letter_path: str | None = None,
    phone: str = "",
    default_answers: dict | None = None,
    max_applications: int = 10,
):
    """
    Postule automatiquement sur une liste d'offres LinkedIn en Candidature simplifiée.

    Le suivi de toutes les candidatures est sauvegardé dans output/applications.xlsx.
    Les offres déjà postulées (dans le fichier de suivi) sont automatiquement ignorées.

    Args:
        job_urls:          Liste d'URLs d'offres LinkedIn.
        cv_path:           Chemin absolu vers le CV (PDF ou DOCX).
        cover_letter_path: Chemin vers la lettre de motivation (optionnel).
        phone:             Numéro de téléphone pour les champs du formulaire.
        default_answers:   Réponses automatiques aux questions du formulaire.
        max_applications:  Nombre maximum de candidatures à déposer (défaut : 10).
    """
    async with BrowserManager(headless=False, account="main") as browser:
        await SessionManager.load(browser)
        ea = EasyApply(
            page=browser.page,
            cv_path=cv_path,
            cover_letter_path=cover_letter_path,
            phone=phone,
            default_answers=default_answers or {},
        )
        results = await ea.apply_bulk(
            job_urls=job_urls,
            delay_between=(12, 30),
            max_applications=max_applications,
        )
        n_applied = sum(1 for r in results if r.get("status") == "applied")
        print(f"\n  ✅ {n_applied}/{len(results)} candidature(s) déposée(s). Suivi : output/applications.xlsx")


# ============================================================
# Exemple 9c : Rechercher + postuler (Easy Apply)  [SCRAPER + MAIN]
# ============================================================

async def exemple_rechercher_et_postuler(
    keywords: str,
    cv_path: str,
    cover_letter_path: str | None = None,
    phone: str = "",
    pays: str = "france",
    type_contrat: list | None = None,
    max_offres: int = 10,
    max_applications: int = 5,
    default_answers: dict | None = None,
):
    """
    Pipeline complet : recherche les offres Easy Apply puis postule automatiquement.

    Étape 1 [compte SCRAPER] : recherche les offres avec le filtre Easy Apply activé.
    Étape 2 [compte MAIN]    : postule sur chaque offre trouvée.

    Args:
        keywords:          Mots-clés de recherche (ex: "data analyst").
        cv_path:           Chemin absolu vers le CV.
        cover_letter_path: Chemin vers la lettre de motivation (optionnel).
        phone:             Numéro de téléphone.
        pays:              Pays de recherche (ex: "france").
        type_contrat:      Types de contrat (ex: ["cdi", "cdd"]).
        max_offres:        Nombre max d'offres à récupérer.
        max_applications:  Nombre max de candidatures à déposer.
        default_answers:   Réponses automatiques aux questions.
    """
    # ── Étape 1 : Recherche des offres Easy Apply [compte SCRAPER] ────────
    print("\n═══ ÉTAPE 1 : Recherche des offres Easy Apply ═══")
    job_urls: list[str] = []
    async with BrowserManager(headless=False, account="scraper") as browser:
        await SessionManager.load(browser)
        search = JobSearch(browser.page)
        job_urls = await search.search(
            keywords=keywords,
            pays=pays,
            type_contrat=type_contrat or [],
            max_offres=max_offres,
            easy_apply_only=True,
        )
    print(f"  → {len(job_urls)} offre(s) Easy Apply trouvée(s).")

    if not job_urls:
        print("  Aucune offre trouvée. Arrêt.")
        return

    # ── Étape 2 : Candidatures [compte MAIN] ──────────────────────────────
    print("\n═══ ÉTAPE 2 : Dépôt des candidatures ═══")
    async with BrowserManager(headless=False, account="main") as browser:
        await SessionManager.load(browser)
        ea = EasyApply(
            page=browser.page,
            cv_path=cv_path,
            cover_letter_path=cover_letter_path,
            phone=phone,
            default_answers=default_answers or {},
        )
        results = await ea.apply_bulk(
            job_urls=job_urls,
            delay_between=(12, 30),
            max_applications=max_applications,
        )
        n_applied = sum(1 for r in results if r.get("status") == "applied")
        print(f"\n  ✅ {n_applied}/{len(results)} candidature(s) déposée(s). Suivi : output/applications.xlsx")


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
    Pipeline complet [compte SCRAPER] :
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
        filtre_poste:  Filtre sur le titre de poste pour les employés.
        max_personnes: Nombre maximum d'employés à scraper par entreprise.
        max_posts:     Nombre maximum de posts à scraper par entreprise.
    """
    async with BrowserManager(headless=False, account="scraper") as browser:
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
    # ──────────────────────────────────────────────────────────────────────
    # Compte SCRAPER (burner) — scraping uniquement
    # ──────────────────────────────────────────────────────────────────────

    # --- Example 1: Search companies ---
    # asyncio.run(exemple_recherche_entreprises())

    # --- Example 2: Search jobs ---
    # asyncio.run(exemple_recherche_emplois())

    # --- Example 4: Scrape employees ---
    # asyncio.run(exemple_employes("https://www.linkedin.com/company/datasulting/"))

    # --- Example 5: Scrape posts ---
    # asyncio.run(exemple_posts("https://www.linkedin.com/company/Datasulting/"))

    # --- Pipeline complet : recherche entreprises → posts + employés ---
    # asyncio.run(pipeline_entreprises(pays="france",secteur="conseil",taille=["11-50", "51-200"],keywords="",max_companies=10,filtre_poste="",max_personnes=10,max_posts=5))

    # ──────────────────────────────────────────────────────────────────────
    # Compte MAIN (principal) — actions sensibles
    # ──────────────────────────────────────────────────────────────────────

    # --- Example 6: Ajouter un contact ---
    # asyncio.run(exemple_ajouter_contact(profile_url="https://www.linkedin.com/in/lucas-congras-80180b3b6/", note="Bonjour, je souhaite rejoindre votre réseau."))

    # --- Example 6b: Ajout en masse ---
    # asyncio.run(exemple_ajouter_contacts_bulk(
    #     profile_urls=[
    #         "https://www.linkedin.com/in/john-doe/",
    #         "https://www.linkedin.com/in/jane-smith/",
    #     ],
    #     note="Bonjour, je souhaite rejoindre votre réseau.",   # optionnel
    # ))

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

    # --- Example 9: Postuler sur une offre Easy Apply ---
    asyncio.run(exemple_postuler(
         job_url="https://www.linkedin.com/jobs/view/4368989325/",
         cv_path=r"C:\Users\LucasCONGRAS\OneDrive - datasulting.com\Bureau\EPF\International - Suede\CV - LM\CV Anglais.pdf",
         cover_letter_path=r"C:\Users\LucasCONGRAS\OneDrive - datasulting.com\Bureau\EPF\International - Suede\CV - LM\Lettre de Motivation - Lucas Congras - Anglais.docx",  # optionnel
         phone="0612345678",
         default_answers={
             "années d'expérience": "3",
             "salaire": "45000",
             # Champs de dates (visas, disponibilités, périodes de travail...)
             # Clé = fragment du label du select (insensible à la casse)
             # Valeur = texte exact de l'option à sélectionner
             "mois : from": "Septembre",   # Mois de début
             "année : from": "2026",       # Année de début
             "mois : to": "Mars",          # Mois de fin
             "année : to": "2027",         # Année de fin (ou année en cours si "en poste")
         },
     ))

    # --- Example 9b: Postuler en masse sur des offres Easy Apply ---
    # asyncio.run(exemple_postuler_bulk(
    #     job_urls=[
    #         "https://www.linkedin.com/jobs/view/1234567890/",
    #         "https://www.linkedin.com/jobs/view/9876543210/",
    #     ],
    #     cv_path="C:/Users/LucasCONGRAS/Documents/CV_Lucas_Congras.pdf",
    #     cover_letter_path="C:/Users/LucasCONGRAS/Documents/Lettre_Motivation.pdf",  # optionnel
    #     phone="0612345678",
    #     max_applications=10,
    # ))

    # --- Example 9c: Rechercher + postuler automatiquement (Easy Apply) ---
    # asyncio.run(exemple_rechercher_et_postuler(
    #     keywords="data analyst",
    #     cv_path="C:/Users/LucasCONGRAS/Documents/CV_Lucas_Congras.pdf",
    #     cover_letter_path="C:/Users/LucasCONGRAS/Documents/Lettre_Motivation.pdf",  # optionnel
    #     phone="0612345678",
    #     pays="france",
    #     type_contrat=["cdi"],
    #     max_offres=20,
    #     max_applications=5,
    #     default_answers={
    #         "années d'expérience": "3",
    #         "salaire souhaité": "45000",
    #         "disponibilité": "immédiatement",
    #     },
    # ))

