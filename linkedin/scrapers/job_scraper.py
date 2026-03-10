"""
JobScraper — scrapes details from a LinkedIn job posting.
"""
import asyncio
import random


class JobScraper:
    """Scrapes details from a single LinkedIn job offer page."""

    def __init__(self, page) -> None:
        self.page = page

    async def scrape(self, job_url: str) -> dict:
        """
        Scrape a LinkedIn job offer.

        Args:
            job_url: Full URL to the job posting
                     (e.g. "https://www.linkedin.com/jobs/view/1234567890/").

        Returns:
            Dict with keys: linkedin_url, job_title, company,
            company_linkedin_url, location, workplace_type, posted_date,
            applicant_count, job_type, experience_level, seniority_level,
            job_description.
        """
        await self.page.goto(job_url, wait_until="domcontentloaded")
        # Wait for the job title to appear so React-rendered content is ready
        try:
            await self.page.wait_for_selector("h1", timeout=10000)
        except Exception:
            pass
        await asyncio.sleep(random.uniform(2, 3))

        result = {
            "linkedin_url": job_url,
            "job_title": None,
            "company": None,
            "company_linkedin_url": None,
            "location": None,
            "workplace_type": None,
            "posted_date": None,
            "applicant_count": None,
            "job_type": None,
            "experience_level": None,
            "seniority_level": None,
            "job_description": None,
        }

        # --- Job title (multiple selectors for robustness) ---
        title_selectors = [
            "h1.t-24",
            ".jobs-unified-top-card__job-title h1",
            ".job-details-jobs-unified-top-card__job-title h1",
            "h1",
        ]
        for sel in title_selectors:
            try:
                elem = self.page.locator(sel).first
                if await elem.count() > 0:
                    text = (await elem.inner_text()).strip()
                    if text:
                        result["job_title"] = text
                        break
            except Exception:
                continue

        # --- Company + company LinkedIn URL ---
        try:
            company_links = await self.page.locator('a[href*="/company/"]').all()
            for link in company_links:
                href = await link.get_attribute("href") or ""
                # Skip sub-pages like /life, /jobs, /about — we want the main profile
                href_path = href.split("?")[0]
                segments = [s for s in href_path.split("/") if s]
                company_idx = next(
                    (i for i, s in enumerate(segments) if s == "company"), None
                )
                if company_idx is not None and len(segments) > company_idx + 2:
                    continue
                text = (await link.inner_text()).strip()
                if text and len(text) > 1:
                    result["company"] = text
                    clean = href_path
                    if not clean.startswith("http"):
                        clean = "https://www.linkedin.com" + clean
                    result["company_linkedin_url"] = clean
                    break
        except Exception:
            pass

        # --- Location / workplace type / posted date / applicant count ---
        try:
            info_spans = await self.page.locator(
                ".job-details-jobs-unified-top-card__primary-description-without-tagline span, "
                ".job-details-jobs-unified-top-card__primary-description-container span, "
                ".jobs-unified-top-card__subtitle-primary-grouping span, "
                ".jobs-unified-top-card__primary-description span, "
                "h1 ~ div span, h1 ~ p span"
            ).all()
            info_texts = []
            for span in info_spans:
                t = (await span.inner_text()).strip()
                if t and t not in ("·", "•", "") and len(t) > 1:
                    info_texts.append(t)

            for t in info_texts:
                tl = t.lower()
                if any(
                    w in tl
                    for w in ["remote", "hybride", "hybrid", "on-site", "présentiel", "télétravail"]
                ):
                    result["workplace_type"] = t
                elif any(
                    w in tl
                    for w in ["il y a", "ago", "heure", "jour", "semaine", "mois", "hour", "day", "week"]
                ):
                    result["posted_date"] = t
                elif any(w in tl for w in ["candidat", "applicant", "postulant"]):
                    result["applicant_count"] = t
                elif result["location"] is None and (
                    "," in t or any(c.isupper() for c in t[1:])
                ):
                    result["location"] = t
        except Exception:
            pass

        # --- Job type + seniority / experience level from "Job details" section ---
        try:
            detail_items = await self.page.locator(
                ".job-details-jobs-unified-top-card__job-insight span, "
                ".jobs-unified-top-card__job-insight span, "
                ".job-details-jobs-unified-top-card__job-insight li, "
                ".jobs-unified-top-card__job-insight li, "
                ".jobs-details__details li"
            ).all()

            for li in detail_items:
                text = (await li.inner_text()).strip()
                tl = text.lower()

                # Job type
                if any(
                    w in tl
                    for w in ["temps plein", "full-time", "temps partiel", "part-time",
                              "contrat", "stage", "intérim", "bénévole"]
                ):
                    result["job_type"] = text

                # Experience / seniority
                if any(
                    w in tl
                    for w in ["junior", "senior", "débutant", "confirmé", "manager",
                              "directeur", "entry", "associate", "mid-senior",
                              "director", "executive", "internship"]
                ):
                    result["experience_level"] = text

                # Seniority level (LinkedIn often has a separate field)
                if any(
                    w in tl
                    for w in ["seniority", "niveau", "ancienneté"]
                ):
                    result["seniority_level"] = text
        except Exception:
            pass

        # --- Full job description (not truncated) ---
        try:
            desc_selectors = [
                ".jobs-description__content",
                ".jobs-description",
                "#job-details",
                "#job-details article",
                "article",
            ]
            for sel in desc_selectors:
                elem = self.page.locator(sel).first
                if await elem.count() > 0:
                    text = (await elem.inner_text()).strip()
                    if len(text) > 100:
                        result["job_description"] = text
                        break
        except Exception:
            pass

        return result
