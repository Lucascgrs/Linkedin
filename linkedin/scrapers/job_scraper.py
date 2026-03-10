"""
JobScraper — scrapes a LinkedIn job offer detail page.
"""
import asyncio
import random


class JobScraper:
    """Scrapes job offer information from a LinkedIn job detail page."""

    # Criteria labels (FR + EN) → normalized field name
    CRITERIA_MAP = {
        # Seniority
        "seniority level":          "seniority_level",
        "niveau de séniorité":      "seniority_level",
        "niveau":                   "seniority_level",
        # Employment type
        "employment type":          "employment_type",
        "type d'emploi":            "employment_type",
        "type de poste":            "employment_type",
        # Job function
        "job function":             "job_function",
        "fonction":                 "job_function",
        "domaine":                  "job_function",
        # Industries
        "industries":               "industries",
        "industrie":                "industries",
        "secteur":                  "industries",
    }

    def __init__(self, page) -> None:
        self.page = page

    async def scrape(self, linkedin_url: str) -> dict:
        """
        Scrape job offer information from a LinkedIn job detail page.

        Args:
            linkedin_url: Full LinkedIn job URL
                          (e.g. "https://www.linkedin.com/jobs/view/1234567890/").

        Returns:
            Dict with keys: linkedin_url, title, company_name, company_url,
            location, posted_time, applicants_count, description,
            seniority_level, employment_type, job_function, industries.
        """
        await self.page.goto(linkedin_url, wait_until="domcontentloaded")
        # Délai aléatoire pour simuler un comportement humain
        await asyncio.sleep(random.uniform(2.5, 5.0))

        result = {
            "linkedin_url":     linkedin_url,
            "title":            None,
            "company_name":     None,
            "company_url":      None,
            "location":         None,
            "posted_time":      None,
            "applicants_count": None,
            "description":      None,
            "seniority_level":  None,
            "employment_type":  None,
            "job_function":     None,
            "industries":       None,
        }

        # Attend que le titre soit visible avant de continuer
        try:
            await self.page.locator("h1.topcard__title").wait_for(
                state="visible", timeout=10000
            )
        except Exception:
            print("  ⚠️ Titre non trouvé dans les 10s, on continue quand même...")

        # --- Title ---
        try:
            title_el = self.page.locator("h1.topcard__title").first
            if await title_el.count() > 0:
                result["title"] = (await title_el.inner_text()).strip()
        except Exception:
            pass

        # --- Company name & URL ---
        try:
            company_link = self.page.locator("a.topcard__org-name-link").first
            if await company_link.count() > 0:
                result["company_name"] = (await company_link.inner_text()).strip()
                href = await company_link.get_attribute("href") or ""
                result["company_url"] = href.split("?")[0]
        except Exception:
            pass

        # --- Location ---
        try:
            flavors = await self.page.locator(".topcard__flavor--bullet").all()
            for flavor in flavors:
                text = (await flavor.inner_text()).strip()
                if text and "applicant" not in text.lower():
                    result["location"] = text
                    break
        except Exception:
            pass

        # --- Posted time ---
        try:
            posted_el = self.page.locator(".posted-time-ago__text").first
            if await posted_el.count() > 0:
                result["posted_time"] = (await posted_el.inner_text()).strip()
        except Exception:
            pass

        # --- Applicants count ---
        try:
            applicants_el = self.page.locator(".num-applicants__caption").first
            if await applicants_el.count() > 0:
                result["applicants_count"] = (await applicants_el.inner_text()).strip()
        except Exception:
            pass

        # --- Job description ---
        try:
            show_more = self.page.locator(
                "button.show-more-less-html__button--more"
            ).first
            if await show_more.count() > 0:
                await show_more.click()
                await asyncio.sleep(random.uniform(0.8, 1.5))

            desc_el = self.page.locator(
                ".show-more-less-html__markup, .description__text--rich"
            ).first
            if await desc_el.count() > 0:
                result["description"] = (await desc_el.inner_text()).strip()
        except Exception:
            pass

        # --- Criteria (seniority, employment type, function, industry) ---
        try:
            items = await self.page.locator(".description__job-criteria-item").all()
            for item in items:
                header_el = item.locator(".description__job-criteria-subheader").first
                value_el  = item.locator(".description__job-criteria-text").first

                if await header_el.count() == 0 or await value_el.count() == 0:
                    continue

                header = (await header_el.inner_text()).strip().lower()
                value  = (await value_el.inner_text()).strip()

                for key, mapped in self.CRITERIA_MAP.items():
                    if key in header:
                        result[mapped] = value
                        break

        except Exception as e:
            print(f"  ⚠️ Erreur extraction critères : {e}")

        return result
