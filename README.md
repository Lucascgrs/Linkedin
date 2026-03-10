# LinkedIn Scraping Toolkit

A clean, class-based Python package for scraping LinkedIn — companies, job offers, employees, and posts — built on top of [joeyism/linkedin-scraper](https://github.com/joeyism/linkedin_scraper) and Playwright.

---

## Architecture

```
linkedin/
├── __init__.py
├── scrapers/
│   ├── __init__.py
│   ├── company_scraper.py      # CompanyScraper
│   ├── job_scraper.py          # JobScraper
│   ├── people_scraper.py       # PeopleScraper
│   └── posts_scraper.py        # PostsScraper
├── search/
│   ├── __init__.py
│   ├── company_search.py       # CompanySearch
│   └── job_search.py           # JobSearch
├── actions/
│   ├── __init__.py
│   └── messenger.py            # LinkedInMessenger
└── utils/
    ├── __init__.py
    ├── stealth_browser.py      # StealthBrowser (anti-bot Playwright context)
    ├── session.py              # SessionManager
    ├── export.py               # ExportUtils (JSON + Excel)
    └── filters.py              # GEO_IDS, INDUSTRY_IDS, … + resolve helpers

Sessions.py          # Entry point: creates / saves the LinkedIn session (run once)
main.py              # Usage examples
requirements.txt     # Dependencies
```

---

## Installation

```bash
# 1. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install the Chromium browser used by Playwright
playwright install chromium
```

---

## Step 1 — Create your session (once)

```bash
python Sessions.py
```

A browser window opens. Log in to LinkedIn manually. The session is saved to `linkedin_session.json`.

> ⚠️ Never commit `linkedin_session.json` to Git — it contains your authentication cookies.

---

## Usage examples

All examples are in `main.py`. Run one by un-commenting it in the `__main__` block.

### Example 1 — Search companies

```python
from linkedin import StealthBrowser, SessionManager, ExportUtils, CompanySearch

async def exemple_recherche_entreprises():
    async with StealthBrowser(headless=False) as browser:
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
```

### Example 2 — Search job offers

```python
from linkedin import StealthBrowser, SessionManager, ExportUtils, JobSearch

async def exemple_recherche_emplois():
    async with StealthBrowser(headless=False) as browser:
        await SessionManager.load(browser)
        search = JobSearch(browser.page)
        results = await search.search_and_scrape(
            keywords="data analyst",
            pays="france",
            date_publiee="semaine",
            mode_travail=["hybride", "remote"],
            type_contrat=["cdi"],
            max_offres=5,
        )
        ExportUtils.to_json_and_excel(results, "output/jobs", "Offres")
```

### Example 3 — Scrape a single company

```python
from linkedin import StealthBrowser, SessionManager, ExportUtils, CompanyScraper

async def exemple_scrape_entreprise(company_url):
    async with StealthBrowser(headless=False) as browser:
        await SessionManager.load(browser)
        scraper = CompanyScraper(browser.page)
        result = await scraper.scrape(company_url)
        ExportUtils.to_json_and_excel([result], "output/company", "Entreprise")
```

### Example 4 — Scrape employees

```python
from linkedin import StealthBrowser, SessionManager, ExportUtils, PeopleScraper

async def exemple_employes(company_url):
    async with StealthBrowser(headless=False) as browser:
        await SessionManager.load(browser)
        scraper = PeopleScraper(browser.page)
        results = await scraper.scrape_company_people(
            company_url=company_url,
            filtre_poste="data",
            max_personnes=20,
        )
        ExportUtils.to_json_and_excel(results, "output/people", "Employés")
```

### Example 5 — Scrape company posts

```python
from linkedin import StealthBrowser, SessionManager, ExportUtils, PostsScraper

async def exemple_posts(company_url):
    async with StealthBrowser(headless=False) as browser:
        await SessionManager.load(browser)
        scraper = PostsScraper(browser.page)
        results = await scraper.scrape(company_url=company_url, limit=10)
        ExportUtils.to_json_and_excel(results, "output/posts", "Posts")
```

### Example 6 — Send a message

```python
from linkedin import StealthBrowser, SessionManager, LinkedInMessenger

async def exemple_message(profile_url, message):
    async with StealthBrowser(headless=False) as browser:
        await SessionManager.load(browser)
        messenger = LinkedInMessenger(browser.page)
        success = await messenger.send_message(
            profile_url=profile_url,
            message=message,
        )
```

---

## Available filter values

### Countries (`pays`)
`france`, `belgique`, `suisse`, `luxembourg`, `allemagne`, `autriche`, `espagne`, `italie`, `portugal`, `pays-bas`, `suede`, `norvege`, `danemark`, `finlande`, `pologne`, `royaume-uni`, `irlande`, `etats-unis`, `canada`, `mexique`, `bresil`, `argentine`, `japon`, `chine`, `inde`, `singapour`, `emirats-arabes-unis`, `australie`, `maroc`, `tunisie`

### Industries (`secteur`)
`software`, `informatique`, `internet`, `telecom`, `finance`, `banque`, `assurance`, `conseil`, `sante`, `pharma`, `industrie`, `automobile`, `energie`, `marketing`, `rh`, `recrutement`, `juridique`, `logistique`, `education`, `media`, `ecommerce`, `restauration`, `tourisme`, …

### Company sizes (`taille`)
`1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+`

### Date posted (`date_publiee`)
`24h`, `semaine`, `mois`

### Workplace type (`mode_travail`)
`presentiel`, `hybride`, `remote`

### Contract type (`type_contrat`)
`cdi`, `cdd`, `stage`, `interim`, `temps-partiel`, `benevole`

### Experience level (`niveau_experience`)
`stage`, `debutant`, `junior`, `associe`, `confirme`, `senior`, `manager`, `directeur`, `executif`

---

## Output

All results are saved in the `output/` directory (created automatically):

| File | Content |
|------|---------|
| `output/companies.json` / `.xlsx` | Company search results |
| `output/jobs.json` / `.xlsx` | Job offer results |
| `output/people.json` / `.xlsx` | Employee profiles |
| `output/posts.json` / `.xlsx` | Company posts |

---

## Notes

- Never commit `linkedin_session.json` to version control.
- Random delays are built in between requests to reduce the risk of account restrictions.
- The `send_messages_bulk` method is capped at 10 messages per session by default.
