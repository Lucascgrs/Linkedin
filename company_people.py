#!/usr/bin/env python3
"""
Récupère les employés d'une entreprise LinkedIn.
Accède à la page /people/ de l'entreprise et scrape les profils visibles.

Limitations LinkedIn :
  - Seuls les profils publics ou dans ton réseau sont visibles
  - Les emails ne sont jamais affichés directement
  - LinkedIn pagine et limite les résultats (~10 par page, max ~100 visibles)
"""
import asyncio
import json
import random
import urllib.parse
from linkedin_scraper.core.browser import BrowserManager


async def scrape_company_people(
    company_url: str,
    filtre_poste: str = "",
    max_personnes: int = 20,
    scrape_profil_detail: bool = False,
) -> list:
    """
    Récupère les employés visibles d'une entreprise.

    Args:
        company_url:          URL LinkedIn de l'entreprise
        filtre_poste:         Filtrer par intitulé de poste, ex: "data", "engineer"
                              (correspond au champ de recherche sur /people/)
        max_personnes:        Nombre max de profils à récupérer
        scrape_profil_detail: Si True, visite chaque profil pour récupérer
                              les infos de contact (email si public, téléphone)
    """
    print("\n" + "=" * 60)
    print("  👥 Scraping des employés d'entreprise")
    print("=" * 60)
    print(f"  Entreprise  : {company_url}")
    print(f"  Filtre poste: {filtre_poste or '(tous)'}")
    print(f"  Max         : {max_personnes}")
    print(f"  Détail profil: {'Oui ⚠️ (lent)' if scrape_profil_detail else 'Non'}")
    print("=" * 60 + "\n")

    # Construire l'URL /people/ avec filtre optionnel
    people_url = company_url.rstrip("/") + "/people/"
    if filtre_poste:
        people_url += "?" + urllib.parse.urlencode({"keywords": filtre_poste})

    async with BrowserManager(headless=False, slow_mo=100) as browser:
        await browser.load_session("linkedin_session.json")
        print("✓ Session chargée\n")

        print(f"🔍 Navigation vers : {people_url}\n")
        await browser.page.goto(people_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        all_people = []
        scroll_count = 0
        max_scrolls = (max_personnes // 8) + 3

        print("📋 Collecte des profils...")
        while len(all_people) < max_personnes and scroll_count < max_scrolls:
            people_on_page = await extract_people_from_page(browser.page)

            # Dédupliquer par URL de profil
            for person in people_on_page:
                if not any(p["profile_url"] == person["profile_url"] for p in all_people):
                    all_people.append(person)
                    if len(all_people) >= max_personnes:
                        break

            print(f"  Scroll {scroll_count + 1} → {len(all_people)} profils collectés")

            if len(all_people) < max_personnes:
                # Scroll pour charger plus
                await browser.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2, 3))
                scroll_count += 1
            else:
                break

        all_people = all_people[:max_personnes]
        print(f"\n✅ {len(all_people)} profils collectés\n")

        # --- Optionnel : scraper les détails de chaque profil ---
        if scrape_profil_detail:
            print("👤 Scraping des détails de chaque profil (contact info)...\n")
            for i, person in enumerate(all_people, 1):
                if not person.get("profile_url"):
                    continue
                print(f"  [{i:2d}/{len(all_people)}] {person.get('name', '?')} — {person.get('profile_url')}")
                try:
                    contact_info = await scrape_profile_contact(browser.page, person["profile_url"])
                    person.update(contact_info)
                    if contact_info.get("email"):
                        print(f"         📧 Email trouvé : {contact_info['email']}")
                    if contact_info.get("website"):
                        print(f"         🌐 Site : {contact_info['website']}")
                except Exception as e:
                    print(f"         ⚠️ Erreur : {e}")
                await asyncio.sleep(random.uniform(3, 5))

        # Affichage résumé
        print("\n" + "=" * 60)
        for i, p in enumerate(all_people[:5], 1):
            print(f"  {i}. {p.get('name', '?'):30s} | {p.get('title', '?')[:35]}")
        if len(all_people) > 5:
            print(f"  ... et {len(all_people) - 5} autres")
        print("=" * 60)

        # Sauvegarde
        output_file = "output_people.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_people, f, ensure_ascii=False, indent=2)
        print(f"\n💾 {len(all_people)} profils → {output_file}")

        return all_people


async def extract_people_from_page(page) -> list:
    """
    Extrait les cartes employés visibles sur la page /people/.
    LinkedIn affiche les employés dans une grille de cartes.
    """
    people = []
    try:
        # Attendre les cartes de profil
        await page.wait_for_selector(
            "a[href*='/in/'], .org-people-profile-card",
            timeout=8000
        )

        # Extraction via JavaScript pour être plus robuste
        raw = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();

            // Sélecteurs des cartes employés LinkedIn /people/
            const cardSelectors = [
                '.org-people-profile-card__card-spacing',
                '.org-people-profile-card',
                '[data-view-name="profile-entity-lockup"]',
                '.artdeco-entity-lockup',
            ];

            let cards = [];
            for (const sel of cardSelectors) {
                cards = document.querySelectorAll(sel);
                if (cards.length > 0) break;
            }

            // Fallback : chercher tous les liens /in/ dans la zone principale
            if (cards.length === 0) {
                const links = document.querySelectorAll('main a[href*="/in/"]');
                links.forEach(link => {
                    const href = link.href.split('?')[0];
                    if (seen.has(href)) return;
                    seen.add(href);

                    // Chercher le nom et titre dans le contexte du lien
                    const container = link.closest('li, div.artdeco-entity-lockup, div[class*="card"]') || link.parentElement;
                    const name = container?.querySelector('span[aria-hidden="true"], .artdeco-entity-lockup__title')?.innerText?.trim() || link.innerText?.trim();
                    const title = container?.querySelector('.artdeco-entity-lockup__subtitle, [class*="subtitle"]')?.innerText?.trim() || '';

                    if (name && name.length > 1) {
                        results.push({ name, title, profile_url: href });
                    }
                });
                return results;
            }

            cards.forEach(card => {
                // URL du profil
                const link = card.querySelector('a[href*="/in/"]');
                if (!link) return;
                const href = link.href.split('?')[0];
                if (seen.has(href)) return;
                seen.add(href);

                // Nom
                const nameEl = card.querySelector(
                    '.artdeco-entity-lockup__title span[aria-hidden="true"], ' +
                    '.org-people-profile-card__profile-title, ' +
                    'span[aria-hidden="true"]'
                );
                const name = nameEl?.innerText?.trim() || '';

                // Titre / poste
                const titleEl = card.querySelector(
                    '.artdeco-entity-lockup__subtitle, ' +
                    '.org-people-profile-card__profile-info, ' +
                    '[class*="subtitle"]'
                );
                const title = titleEl?.innerText?.trim() || '';

                // Localisation (parfois affichée)
                const locationEl = card.querySelector('[class*="caption"], [class*="location"]');
                const location = locationEl?.innerText?.trim() || '';

                if (name) {
                    results.push({ name, title, location, profile_url: href });
                }
            });

            return results;
        }""")

        people = raw if raw else []

    except Exception as e:
        print(f"  ⚠️ Erreur extraction employés : {e}")

    return people


async def scrape_profile_contact(page, profile_url: str) -> dict:
    """
    Scrape les infos de contact d'un profil (email, téléphone, site web).
    LinkedIn les cache derrière /overlay/contact-info/ — accessible si connexion.
    """
    contact = {
        "email": None,
        "phone": None,
        "website": None,
        "twitter": None,
    }

    try:
        # Aller sur la page du profil d'abord
        await page.goto(profile_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Cliquer sur "Coordonnées" pour ouvrir le modal
        contact_btn_selectors = [
            'a[href*="overlay/contact-info"]',
            'a[id*="contact-info"]',
            'a:has-text("Coordonnées")',
            'a:has-text("Contact info")',
        ]
        clicked = False
        for sel in contact_btn_selectors:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                await btn.click()
                await asyncio.sleep(2)
                clicked = True
                break

        if not clicked:
            return contact

        # Extraire les infos du modal
        modal = page.locator('.pv-profile-section__section-info, .pv-contact-info__contact-type, section.pv-contact-info').first
        if await modal.count() == 0:
            modal = page.locator('[data-test-modal]').first

        if await modal.count() > 0:
            text = (await modal.inner_text()).strip()
        else:
            # Fallback : tout le modal ouvert
            text = await page.locator('div[role="dialog"]').first.inner_text()

        # Parser email
        import re
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
        if email_match:
            contact["email"] = email_match.group(0)

        # Parser téléphone
        phone_match = re.search(r'(\+?\d[\d\s\-().]{7,20})', text)
        if phone_match:
            contact["phone"] = phone_match.group(0).strip()

        # Parser site web
        web_links = await page.locator('div[role="dialog"] a[href^="http"]').all()
        for link in web_links:
            href = await link.get_attribute("href") or ""
            if "linkedin.com" not in href:
                contact["website"] = href
                break

        # Fermer le modal
        close_btn = page.locator('button[aria-label*="Fermer"], button[aria-label*="Close"]').first
        if await close_btn.count() > 0:
            await close_btn.click()

    except Exception as e:
        pass  # Silencieux — les infos de contact sont souvent inaccessibles

    return contact


# ============================================================
# ▶️  LANCEMENT
# ============================================================

if __name__ == "__main__":
    asyncio.run(scrape_company_people(
        company_url="https://www.linkedin.com/company/microsoft/",
        filtre_poste="data",         # "" pour tous les postes
        max_personnes=20,
        scrape_profil_detail=False,  # True pour tenter de récupérer emails/téléphones
    ))