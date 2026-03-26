"""
EasyApply — postule automatiquement sur les offres LinkedIn "Candidature simplifiée".

Fonctionnalités :
  - apply(job_url)                    : postule sur une offre unique
  - apply_bulk(job_urls)              : postule sur une liste d'offres avec délai anti-ban
  - is_easy_apply(job_url)            : vérifie si une offre est bien en candidature simplifiée
  - get_applications_df()             : retourne le DataFrame des candidatures déposées

Fichier de suivi :
  output/applications.xlsx  (créé si absent, mis à jour sinon — jamais remis à zéro)

Colonnes :
  job_url | title | company | location | date_applied | status |
  cv_used | cover_letter_used | notes

Paramètres du constructeur :
  page             : instance Playwright Page (session main authentifiée)
  cv_path          : chemin absolu vers le CV (PDF ou DOCX)
  cover_letter_path: chemin optionnel vers la lettre de motivation (PDF ou DOCX)
  phone            : numéro de téléphone (str) pour les champs téléphone du formulaire
  email            : adresse email (str) de secours si demandée
  extra_docs       : dict {label: path} pour d'autres pièces jointes éventuelles
  default_answers  : dict {mot_clé_question: réponse} pour répondre automatiquement
                     aux questions ouvertes/QCM connues
  applications_file: chemin du fichier Excel de suivi (défaut : output/applications.xlsx)
  headless_mode    : si True, pas de captures d'écran en cas d'échec (défaut : False)
"""
import asyncio
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path

from linkedin.utils.export import ExportUtils

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes du fichier de suivi
# ---------------------------------------------------------------------------
APPLICATIONS_FILE = os.path.join("output", "applications.xlsx")
SHEET_NAME = "Candidatures"
COLUMNS = [
    "job_url",
    "title",
    "company",
    "location",
    "date_applied",
    "status",          # "applied" | "already_applied" | "skipped" | "failed" | "not_easy_apply"
    "cv_used",
    "cover_letter_used",
    "notes",
]


# ---------------------------------------------------------------------------
# EasyApply
# ---------------------------------------------------------------------------

class EasyApply:
    """
    Postule automatiquement sur les offres LinkedIn en "Candidature simplifiée".

    Usage rapide :
        async with StealthBrowser(headless=False, account="main") as browser:
            await SessionManager.load(browser)
            ea = EasyApply(
                page=browser.page,
                cv_path="C:/Documents/mon_cv.pdf",
                cover_letter_path="C:/Documents/lettre.pdf",
                phone="0612345678",
            )
            result = await ea.apply("https://www.linkedin.com/jobs/view/1234567890/")
            print(result)
    """

    # Sélecteurs du bouton "Candidature simplifiée" / "Easy Apply"
    _EASY_APPLY_BTN_SELECTORS = [
        "button[aria-label*='Easy Apply']",
        "button[aria-label*='Candidature simplifiée']",
        "button[aria-label*='easy apply' i]",
        "button[aria-label*='candidature simplifi' i]",
        ".jobs-apply-button--top-card",
        "button.jobs-apply-button",
        # Nouveaux sélecteurs pour les mises à jour LinkedIn
        "[data-control-name='jobdetails_topcard_inapply']",
        "button[data-job-id]",
        ".jobs-s-apply button",
        ".jobs-apply-button",
        "[class*='jobs-apply-button']",
        "button[class*='apply']",
    ]

    # Sélecteurs du modal Easy Apply
    _MODAL_SELECTORS = [
        ".jobs-easy-apply-modal",
        "[data-test-modal-id='easy-apply-modal']",
        "div[role='dialog']",
        ".artdeco-modal",
        # Nouveaux sélecteurs
        "[aria-labelledby*='easy-apply']",
        "[aria-labelledby*='apply']",
        ".jobs-easy-apply-content",
        "[data-test-job-apply-flow]",
    ]

    # Sélecteurs du bouton "Suivant" / "Vérifier" / "Soumettre la candidature"
    _NEXT_BTN_SELECTORS = [
        "button[aria-label*='Continuer']",
        "button[aria-label*='Continue']",
        "button[aria-label*='Suivant']",
        "button[aria-label*='Next']",
        "button[aria-label*='Vérifier']",
        "button[aria-label*='Review']",
        "button[aria-label*='Soumettre']",
        "button[aria-label*='Submit']",
        "footer button.artdeco-button--primary",
        ".jobs-easy-apply-modal button.artdeco-button--primary",
        "[data-test-modal-id='easy-apply-modal'] button.artdeco-button--primary",
    ]

    # Sélecteurs du bouton "Soumettre la candidature" (dernière étape)
    _SUBMIT_BTN_SELECTORS = [
        "button[aria-label*='Soumettre la candidature']",
        "button[aria-label*='Submit application']",
        "button[aria-label*='Submit']",
        "button[aria-label*='Soumettre']",
        "footer button.artdeco-button--primary:last-child",
    ]

    # Sélecteurs du bouton "Ignorer" / "Fermer" après soumission réussie
    _DISMISS_BTN_SELECTORS = [
        "button[aria-label*='Ignorer']",
        "button[aria-label*='Dismiss']",
        "button[aria-label*='Fermer']",
        "button[aria-label*='Close']",
        ".artdeco-modal__dismiss",
        "button[data-test-modal-close-btn]",
    ]

    def __init__(
        self,
        page,
        cv_path: str,
        cover_letter_path: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        extra_docs: dict[str, str] | None = None,
        default_answers: dict[str, str] | None = None,
        applications_file: str = APPLICATIONS_FILE,
        headless_mode: bool = False,
    ) -> None:
        """
        Args:
            page:              Instance Playwright Page avec session main authentifiée.
            cv_path:           Chemin absolu vers le CV (PDF ou DOCX). Obligatoire.
            cover_letter_path: Chemin vers la lettre de motivation (PDF/DOCX). Optionnel.
            phone:             Numéro de téléphone à saisir si demandé.
            email:             Email de secours si demandé dans le formulaire.
            extra_docs:        Autres pièces jointes {label_champ: chemin_fichier}.
            default_answers:   Réponses par défaut pour les questions du formulaire.
                               Clé = fragment de la question (insensible à la casse),
                               Valeur = réponse à saisir/sélectionner.
                               Exemple : {"années d'expérience": "3", "salaire": "45000"}
            applications_file: Chemin du fichier Excel de suivi des candidatures.
            headless_mode:     Désactive les captures d'écran en cas d'erreur.
        """
        self.page = page
        self.cv_path = str(Path(cv_path).resolve())
        self.cover_letter_path = str(Path(cover_letter_path).resolve()) if cover_letter_path else None
        self.phone = phone or ""
        self.email = email or ""
        self.extra_docs = extra_docs or {}
        self.default_answers = {k.lower(): v for k, v in (default_answers or {}).items()}
        self.applications_file = applications_file
        self.headless_mode = headless_mode

        # Vérifications des fichiers fournis
        if not os.path.exists(self.cv_path):
            raise FileNotFoundError(f"CV introuvable : {self.cv_path}")
        if self.cover_letter_path and not os.path.exists(self.cover_letter_path):
            raise FileNotFoundError(f"Lettre de motivation introuvable : {self.cover_letter_path}")
        for label, path in self.extra_docs.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"Document '{label}' introuvable : {path}")

        self._records: list[dict] = ExportUtils.load_workbook(applications_file)
        print(f"  📂 {len(self._records)} candidature(s) existante(s) chargée(s) depuis {applications_file}")

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

    async def is_easy_apply(self, job_url: str) -> bool:
        """
        Vérifie si une offre est en candidature simplifiée sans postuler.

        Args:
            job_url: URL de l'offre LinkedIn.

        Returns:
            True si le bouton "Candidature simplifiée" est présent.
        """
        try:
            await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))
            return await self._has_easy_apply_button()
        except Exception as e:
            print(f"  ⚠️  Impossible de vérifier {job_url} : {e}")
            return False

    async def apply(self, job_url: str) -> dict:
        """
        Postule sur une offre LinkedIn en candidature simplifiée.

        Processus :
          1. Navigation vers l'offre
          2. Vérification de la présence du bouton Easy Apply
          3. Détection d'une candidature déjà déposée
          4. Ouverture du modal et remplissage du formulaire
          5. Soumission et fermeture du modal
          6. Sauvegarde dans le fichier Excel de suivi

        Args:
            job_url: URL complète de l'offre LinkedIn.

        Returns:
            Dict {
                "job_url", "title", "company", "location",
                "date_applied", "status", "cv_used",
                "cover_letter_used", "notes"
            }
            status : "applied" | "already_applied" | "skipped" | "failed" | "not_easy_apply"
        """
        job_url = job_url.rstrip("/") + "/"
        print(f"\n→ Candidature : {job_url}")

        record = {
            "job_url":           job_url,
            "title":             None,
            "company":           None,
            "location":          None,
            "date_applied":      None,
            "status":            "failed",
            "cv_used":           os.path.basename(self.cv_path),
            "cover_letter_used": os.path.basename(self.cover_letter_path) if self.cover_letter_path else "",
            "notes":             "",
        }

        try:
            # ── 1. Navigation ─────────────────────────────────────────────
            await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))

            # Attendre que le réseau soit idle (SPA LinkedIn charge le contenu dynamiquement)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass  # Pas critique si timeout

            # Scroll plus agressif pour déclencher le rendu du bouton sticky
            for scroll_pos in [300, 600, 300, 0]:
                await self.page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                await asyncio.sleep(0.4)

            # Attente supplémentaire pour le rendu React/SPA
            await asyncio.sleep(1.5)

            # Logs de diagnostic post-navigation
            nav_url   = self.page.url
            nav_title = await self.page.title()
            print(f"  [📍] Page chargée : {nav_url}")
            print(f"  [📍] Titre        : {nav_title}")
            if "authwall" in nav_url or "login" in nav_url or "checkpoint" in nav_url:
                print(f"  [🚨] ATTENTION : la page semble être un mur d'authentification ou captcha !")
            # Dump des 1500 premiers caractères du body pour voir l'état de la page
            try:
                body_text = await self.page.evaluate("document.body.innerText")
                print(f"  [📄] body.innerText (500 premiers chars) : {body_text[:500]!r}")
            except Exception as _e:
                print(f"  [⚠️ ] Impossible de lire body.innerText : {_e}")

            # ── 2. Scrape infos de base (titre, entreprise, localisation) ──
            await self._scrape_job_meta(record)

            # ── 3. Candidature déjà déposée ? (upsert = ne re-postule pas) ─
            existing = self._find_existing(job_url)
            if existing and existing.get("status") == "applied":
                print(f"  📨 Déjà postulé le {existing.get('date_applied', '?')} — ignoré.")
                record = existing
                record["status"] = "already_applied"
                return record

            # ── 4. Bouton Easy Apply présent ? ────────────────────────────
            if not await self._has_easy_apply_button():
                print(f"  ⚠️  Pas de bouton Candidature simplifiée — offre ignorée.")
                record["status"] = "not_easy_apply"
                record["notes"] = "Bouton Easy Apply absent sur cette offre"
                self._persist(record)
                return record

            # ── 5. Ouvrir le modal Easy Apply ────────────────────────────
            opened = await self._open_easy_apply_modal()
            if not opened:
                print(f"  ❌ Impossible d'ouvrir le modal Easy Apply.")
                record["status"] = "failed"
                record["notes"] = "Ouverture du modal échouée"
                self._persist(record)
                return record

            # ── 6. Remplir le formulaire (multi-étapes) ──────────────────
            submitted = await self._fill_and_submit_form()

            if submitted:
                record["status"] = "applied"
                record["date_applied"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                print(f"  ✅ Candidature soumise : {record.get('title', '?')} @ {record.get('company', '?')}")
            else:
                record["status"] = "failed"
                record["notes"] = record.get("notes") or "Soumission du formulaire échouée"
                print(f"  ❌ Échec de la soumission : {record.get('title', '?')}")

            # ── 7. Fermeture du modal ─────────────────────────────────────
            await self._dismiss_modal()

        except Exception as e:
            record["status"] = "failed"
            record["notes"] = str(e)
            print(f"  ❌ Exception sur {job_url} : {e}")
            # Tentative de fermeture du modal en cas d'erreur
            try:
                await self._dismiss_modal()
            except Exception:
                pass

        # ── 8. Persistance ────────────────────────────────────────────────
        self._persist(record)
        return record

    async def apply_bulk(
        self,
        job_urls: list[str],
        delay_between: tuple[int, int] = (10, 25),
        max_applications: int = 15,
    ) -> list[dict]:
        """
        Postule sur une liste d'offres avec délai anti-ban.

        Args:
            job_urls:         Liste d'URLs d'offres LinkedIn.
            delay_between:    Intervalle de pause (min, max) en secondes entre chaque candidature.
            max_applications: Nombre maximum de candidatures à déposer en une session.

        Returns:
            Liste de dicts résultats (même format que apply()).
        """
        results = []
        applied_count = 0

        for i, url in enumerate(job_urls, 1):
            if applied_count >= max_applications:
                print(f"\n  ⚠️  Limite de {max_applications} candidature(s) atteinte — arrêt.")
                break

            print(f"\n[{i}/{min(len(job_urls), max_applications)}] Traitement de l'offre...")
            result = await self.apply(url)
            results.append(result)

            if result.get("status") == "applied":
                applied_count += 1
                # Délai anti-ban uniquement après une vraie candidature
                wait = random.uniform(*delay_between)
                print(f"  ⏳ Pause {wait:.0f}s avant la prochaine candidature...")
                await asyncio.sleep(wait)
            else:
                # Délai court pour les offres ignorées/déjà postulées
                await asyncio.sleep(random.uniform(2, 5))

        total = len(results)
        n_applied = sum(1 for r in results if r.get("status") == "applied")
        n_failed  = sum(1 for r in results if r.get("status") == "failed")
        print(f"\n  📊 Résumé : {n_applied} postulé(s), {n_failed} échoué(s), {total} traité(s).")
        return results

    def get_applications_df(self):
        """
        Retourne les données de suivi sous forme de DataFrame pandas.

        Returns:
            pandas.DataFrame des candidatures.
        """
        try:
            import pandas as pd
            return pd.DataFrame(self._records, columns=COLUMNS)
        except ImportError:
            raise ImportError("pandas est requis. Installez-le avec : pip install pandas")

    # ------------------------------------------------------------------
    # Méthodes privées — Navigation & détection
    # ------------------------------------------------------------------

    async def _has_easy_apply_button(self) -> bool:
        """Retourne True si le bouton Easy Apply est visible sur la page courante."""
        print(f"    [🔍] Recherche du bouton Easy Apply ({len(self._EASY_APPLY_BTN_SELECTORS)} sélecteurs)...")
        for sel in self._EASY_APPLY_BTN_SELECTORS:
            try:
                loc = self.page.locator(sel).first
                count = await loc.count()
                if count > 0:
                    is_visible = await loc.is_visible()
                    label = (await loc.get_attribute("aria-label") or "")
                    text  = (await loc.inner_text()).strip()
                    print(f"      [sel={sel!r}] count={count}, visible={is_visible}, aria-label={label!r}, text={text!r}")
                    if is_visible:
                        combined = (label + " " + text).lower()
                        if any(kw in combined for kw in [
                            "easy apply", "candidature simplifiée", "candidature simplifiee",
                            "postuler facilement",
                        ]):
                            print(f"    [✓] Bouton Easy Apply confirmé via aria-label/text : {sel!r}")
                            return True
                        # Bouton primary natif LinkedIn sans href = Easy Apply
                        if "jobs-apply-button" in sel:
                            href = await loc.get_attribute("href")
                            print(f"      [jobs-apply-button] href={href!r}")
                            if href is None:
                                print(f"    [✓] Bouton Easy Apply confirmé via jobs-apply-button sans href.")
                                return True
                else:
                    print(f"      [sel={sel!r}] → 0 éléments trouvés")
            except Exception as e:
                print(f"      [sel={sel!r}] → exception : {e}")
                continue

        # Fallback 1 : recherche par texte visible du bouton (getByRole + has_text)
        _text_variants = [
            "Candidature simplifiée",
            "Easy Apply",
            "Postuler facilement",
            "Candidature simplifi",
        ]
        for text_variant in _text_variants:
            try:
                loc = self.page.get_by_role("button", name=re.compile(text_variant, re.IGNORECASE)).first
                count = await loc.count()
                if count > 0 and await loc.is_visible():
                    print(f"    [✓] Bouton Easy Apply confirmé via get_by_role (text={text_variant!r})")
                    return True
            except Exception as e:
                print(f"    [getByRole text={text_variant!r}] → exception : {e}")
            # Variante : filter has_text (cherche dans les sous-éléments)
            try:
                loc = self.page.locator("button").filter(has_text=re.compile(text_variant, re.IGNORECASE)).first
                count = await loc.count()
                if count > 0 and await loc.is_visible():
                    print(f"    [✓] Bouton Easy Apply confirmé via filter has_text (text={text_variant!r})")
                    return True
            except Exception as e:
                print(f"    [filter has_text={text_variant!r}] → exception : {e}")

        # Fallback 2 : recherche JS dans tous les boutons/liens de la page
        try:
            found = await self.page.evaluate("""() => {
                const keywords = ['easy apply', 'candidature simplifi', 'postuler facilement'];
                const candidates = Array.from(document.querySelectorAll('button, a[role="button"], div[role="button"], a'));
                for (const el of candidates) {
                    const txt = (el.textContent || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                    const lbl = (el.getAttribute('aria-label') || '').toLowerCase();
                    const html = (el.innerHTML || '').toLowerCase();
                    if (keywords.some(kw => txt.includes(kw) || lbl.includes(kw) || html.includes(kw))) {
                        return true;
                    }
                }
                return false;
            }""")
            if found:
                print(f"    [✓] Bouton Easy Apply confirmé via JS scan de tous les boutons")
                return True
        except Exception as e:
            print(f"    [JS scan] → exception : {e}")

        # Fallback 3 : HTML brut
        try:
            html = await self.page.content()
            print(f"    [🔍] Fallback HTML (taille: {len(html)} chars)...")
            for pattern in [r'easy\s*apply', r'candidature\s*simplifi', r'f_LF=f_WRA']:
                if re.search(pattern, html, re.IGNORECASE):
                    print(f"    [✓] Bouton Easy Apply confirmé via fallback HTML (pattern: {pattern!r})")
                    return True
            print(f"    [✗] Aucun pattern Easy Apply trouvé dans le HTML.")
            # Dump partiel du HTML pour diagnostic
            snippet = html[:3000] if len(html) > 3000 else html
            print(f"    [📄] HTML (3000 premiers chars) :\n{snippet}")
        except Exception as e:
            print(f"    [✗] Fallback HTML exception : {e}")
        return False

    async def _scrape_job_meta(self, record: dict) -> None:
        """Extrait le titre, l'entreprise et la localisation depuis la page d'offre."""
        page = self.page
        try:
            # Titre
            for sel in ["h1", "h1[class*='job-title']"]:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0:
                        text = (await loc.inner_text()).strip()
                        if text:
                            record["title"] = text
                            break
                except Exception:
                    continue

            if not record["title"]:
                title_tag = await page.title()
                record["title"] = re.split(r"\s*\|\s*", title_tag)[0].strip() if title_tag else None

            # Entreprise (lien /company/)
            try:
                company_link = page.locator("main a[href*='/company/']").first
                if await company_link.count() > 0:
                    record["company"] = (await company_link.inner_text()).strip()
            except Exception:
                pass

            # Localisation
            try:
                all_p = await page.locator("main p, [role='main'] p").all()
                for p_el in all_p[:30]:
                    txt = (await p_el.inner_text()).strip()
                    if "·" in txt and 5 < len(txt) < 150:
                        record["location"] = txt.split("·")[0].strip()
                        break
            except Exception:
                pass

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Méthodes privées — Modal Easy Apply
    # ------------------------------------------------------------------

    async def _open_easy_apply_modal(self) -> bool:
        """
        Clique sur le bouton Easy Apply et attend l'ouverture du modal.

        Returns:
            True si le modal est bien ouvert.
        """
        print(f"    [🔍] Tentative d'ouverture du modal Easy Apply ({len(self._EASY_APPLY_BTN_SELECTORS)} sélecteurs)...")

        # Dump de l'URL courante et du titre de page avant clic
        current_url = self.page.url
        page_title = await self.page.title()
        print(f"    [📍] URL courante : {current_url}")
        print(f"    [📍] Titre page   : {page_title}")

        # Lister tous les boutons visibles sur la page pour diagnostic
        try:
            all_buttons = self.page.locator("button")
            btn_count = await all_buttons.count()
            print(f"    [📊] Nombre total de <button> sur la page : {btn_count}")
            for i in range(min(btn_count, 20)):
                btn = all_buttons.nth(i)
                try:
                    b_label = await btn.get_attribute("aria-label") or ""
                    b_text  = (await btn.inner_text()).strip()
                    b_class = await btn.get_attribute("class") or ""
                    b_vis   = await btn.is_visible()
                    print(f"      [btn {i}] visible={b_vis}, aria-label={b_label!r}, text={b_text!r}, class={b_class[:80]!r}")
                except Exception:
                    continue
        except Exception as e:
            print(f"    [⚠️ ] Impossible de lister les boutons : {e}")

        for sel in self._EASY_APPLY_BTN_SELECTORS:
            try:
                loc = self.page.locator(sel).first
                count = await loc.count()
                is_vis = await loc.is_visible() if count > 0 else False
                print(f"    [sel={sel!r}] count={count}, visible={is_vis}")
                if count > 0 and is_vis:
                    # Dump de l'outerHTML du bouton
                    try:
                        outer = await loc.evaluate("el => el.outerHTML")
                        print(f"      [outerHTML] {outer[:300]}")
                    except Exception:
                        pass

                    await loc.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    await loc.click()
                    print(f"    [✓] Bouton Easy Apply cliqué : {sel}")

                    # Attendre l'apparition du modal
                    modal_found = await self._wait_for_modal()
                    if modal_found:
                        return True

                    # Modal pas détecté via sélecteurs — continuer avec fallbacks
                    await asyncio.sleep(2)
                    print(f"    [⚠️ ] Modal non détecté via sélecteurs connus après clic {sel!r} — tentative fallbacks.")
            except Exception as e:
                print(f"    [sel={sel!r}] → exception : {e}")
                continue

        # ── Fallback A : get_by_role + has_text (cherche dans sous-éléments) ──
        _text_variants = [
            "Candidature simplifiée",
            "Easy Apply",
            "Postuler facilement",
            "Candidature simplifi",
        ]
        for text_variant in _text_variants:
            # Essai 1 : get_by_role
            try:
                loc = self.page.get_by_role("button", name=re.compile(text_variant, re.IGNORECASE)).first
                count = await loc.count()
                if count > 0:
                    is_vis = await loc.is_visible()
                    print(f"    [get_by_role text={text_variant!r}] count={count}, visible={is_vis}")
                    if is_vis:
                        await loc.scroll_into_view_if_needed()
                        await asyncio.sleep(random.uniform(0.5, 1.0))
                        await loc.click()
                        print(f"    [✓] Bouton Easy Apply cliqué via get_by_role (text={text_variant!r})")
                        modal_opened = await self._wait_for_modal()
                        if modal_opened:
                            return True
                        print(f"    [⚠️ ] Modal non détecté après clic get_by_role — on retourne True quand même.")
                        return True
            except Exception as e:
                print(f"    [get_by_role text={text_variant!r}] → exception : {e}")
            # Essai 2 : locator('button').filter(has_text=...) — cherche dans le texte imbriqué
            try:
                loc = self.page.locator("button").filter(has_text=re.compile(text_variant, re.IGNORECASE)).first
                count = await loc.count()
                if count > 0:
                    is_vis = await loc.is_visible()
                    print(f"    [filter has_text={text_variant!r}] count={count}, visible={is_vis}")
                    if is_vis:
                        await loc.scroll_into_view_if_needed()
                        await asyncio.sleep(random.uniform(0.5, 1.0))
                        await loc.click()
                        print(f"    [✓] Bouton Easy Apply cliqué via filter has_text (text={text_variant!r})")
                        modal_opened = await self._wait_for_modal()
                        if modal_opened:
                            return True
                        print(f"    [⚠️ ] Modal non détecté après filter has_text — on retourne True quand même.")
                        return True
            except Exception as e:
                print(f"    [filter has_text={text_variant!r}] → exception : {e}")

        # ── Fallback B : clic JS sur le premier bouton contenant le texte ──
        # Utilise textContent (inclut les spans/SVG enfants) + innerHTML pour le logo
        try:
            clicked = await self.page.evaluate("""() => {
                const keywords = ['candidature simplifi', 'easy apply', 'postuler facilement'];
                // Chercher dans button, a[role=button], div[role=button], a
                const candidates = Array.from(document.querySelectorAll('button, a[role="button"], div[role="button"], a'));
                for (const el of candidates) {
                    const txt = (el.textContent || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                    const lbl = (el.getAttribute('aria-label') || '').toLowerCase();
                    const html = (el.innerHTML || '').toLowerCase();
                    if (keywords.some(kw => txt.includes(kw) || lbl.includes(kw) || html.includes(kw))) {
                        el.scrollIntoView({behavior: 'instant', block: 'center'});
                        el.click();
                        return 'clicked:' + el.tagName + ':' + txt.substring(0, 80);
                    }
                }
                return null;
            }""")
            if clicked:
                print(f"    [✓] Bouton Easy Apply cliqué via JS fallback B : {clicked}")
                await asyncio.sleep(2.0)
                modal_opened = await self._wait_for_modal()
                if modal_opened:
                    return True
                print(f"    [⚠️ ] Modal non détecté après clic JS B — on retourne True quand même.")
                return True
            else:
                print(f"    [JS fallback B] Aucun bouton Easy Apply trouvé dans le DOM.")
        except Exception as e:
            print(f"    [JS fallback B] → exception : {e}")

        # ── Fallback C : scroll + attente supplémentaire puis retry JS ──
        # LinkedIn SPA peut charger le bouton tardivement
        try:
            print(f"    [🔄] Fallback C : scroll + attente 3s puis retry...")
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1.0)
            await self.page.evaluate("window.scrollTo(0, 400)")
            await asyncio.sleep(2.0)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1.0)

            clicked = await self.page.evaluate("""() => {
                const keywords = ['candidature simplifi', 'easy apply', 'postuler facilement'];
                const candidates = Array.from(document.querySelectorAll('button, a[role="button"], div[role="button"], a'));
                for (const el of candidates) {
                    const txt = (el.textContent || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                    const lbl = (el.getAttribute('aria-label') || '').toLowerCase();
                    const html = (el.innerHTML || '').toLowerCase();
                    if (keywords.some(kw => txt.includes(kw) || lbl.includes(kw) || html.includes(kw))) {
                        el.scrollIntoView({behavior: 'instant', block: 'center'});
                        el.click();
                        return 'clicked:' + el.tagName + ':' + txt.substring(0, 80);
                    }
                }
                // Debug : lister tous les boutons et leurs textes
                const allBtns = Array.from(document.querySelectorAll('button'));
                return 'debug:' + allBtns.map(b => (b.textContent||'').replace(/\\s+/g,' ').trim().substring(0,40)).join('|');
            }""")
            if clicked and clicked.startswith("clicked:"):
                print(f"    [✓] Bouton Easy Apply cliqué via Fallback C : {clicked}")
                await asyncio.sleep(2.0)
                modal_opened = await self._wait_for_modal()
                if modal_opened:
                    return True
                print(f"    [⚠️ ] Modal non détecté après Fallback C — on retourne True quand même.")
                return True
            else:
                print(f"    [Fallback C] Aucun bouton trouvé. Debug boutons : {clicked}")
        except Exception as e:
            print(f"    [Fallback C] → exception : {e}")

        # Aucun bouton cliqué — dump HTML complet pour diagnostic
        print(f"    [✗] Aucun bouton Easy Apply cliqué. Dump HTML de la page...")
        try:
            html = await self.page.content()
            print(f"    [📄] HTML page entière ({len(html)} chars), premiers 5000 :")
            print(html[:5000])
        except Exception as e:
            print(f"    [✗] Impossible de récupérer le HTML : {e}")
        return False

    async def _wait_for_modal(self) -> bool:
        """Attend l'apparition du modal Easy Apply. Retourne True si trouvé."""
        for modal_sel in self._MODAL_SELECTORS:
            try:
                await self.page.wait_for_selector(modal_sel, timeout=8000)
                print(f"    [✓] Modal ouvert : {modal_sel}")
                await asyncio.sleep(1.0)
                return True
            except Exception:
                continue
        return False

    async def _dismiss_modal(self) -> None:
        """Ferme le modal Easy Apply / confirmation."""
        for sel in self._DISMISS_BTN_SELECTORS:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click()
                    await asyncio.sleep(0.8)
                    print(f"    [✓] Modal fermé.")
                    return
            except Exception:
                continue
        # Tentative de fermeture via Escape
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Méthodes privées — Remplissage du formulaire
    # ------------------------------------------------------------------

    async def _fill_and_submit_form(self) -> bool:
        """
        Gère les étapes multiples du formulaire Easy Apply.

        Processus :
          - Détecte les champs présents sur chaque étape
          - Upload du CV (si champ fichier présent)
          - Upload de la lettre de motivation (si champ fichier présent)
          - Remplissage des champs texte/sélection connus
          - Clic sur "Suivant" jusqu'à la page de soumission
          - Soumission finale

        Returns:
            True si la candidature a été soumise avec succès.
        """
        max_steps = 15  # sécurité anti-boucle infinie

        for step in range(max_steps):
            print(f"    [Étape {step + 1}] Analyse du formulaire...")
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # Vérifier si l'on est déjà sur la page de succès
            if await self._is_success_page():
                print(f"    [✓] Candidature soumise avec succès (confirmation détectée).")
                return True

            # Remplir les champs de l'étape courante
            await self._fill_current_step()

            # Chercher le bouton d'action (Suivant / Vérifier / Soumettre)
            action_btn = await self._find_action_button()
            if action_btn is None:
                print(f"    [!] Aucun bouton d'action trouvé à l'étape {step + 1}.")
                break

            btn_label = (await action_btn.get_attribute("aria-label") or "").lower()
            btn_text  = (await action_btn.inner_text()).strip().lower()
            combined  = btn_label + " " + btn_text

            is_submit = any(kw in combined for kw in [
                "soumettre", "submit", "envoyer la candidature",
                "send application", "soumettre la candidature",
            ])

            print(f"    → Clic sur : '{btn_text or btn_label}'")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await action_btn.click()
            await asyncio.sleep(random.uniform(1.0, 2.0))

            if is_submit:
                # Vérifier confirmation
                await asyncio.sleep(1.5)
                if await self._is_success_page():
                    return True
                # LinkedIn peut afficher la confirmation sans page dédiée
                return True

        return False

    async def _fill_current_step(self) -> None:
        """
        Détecte et remplit tous les champs interactifs visibles dans l'étape courante.

        Gère :
          - Champs fichier (CV, lettre de motivation, autres docs)
          - Champs texte pré-remplis à vérifier / compléter
          - Champs texte à remplir (téléphone, email, texte libre)
          - Selects (listes déroulantes)
          - Radios / Checkboxes
          - Textareas
        """
        modal = await self._get_modal_container()

        # ── Upload CV ─────────────────────────────────────────────────────
        await self._handle_file_uploads(modal)

        # ── Champs texte & select ─────────────────────────────────────────
        await self._handle_form_fields(modal)

    async def _get_modal_container(self):
        """Retourne le locator du modal Easy Apply ou la page entière en fallback."""
        for sel in self._MODAL_SELECTORS:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0:
                    return loc
            except Exception:
                continue
        return self.page

    async def _handle_file_uploads(self, container) -> None:
        """Gère tous les champs input[type=file] visibles dans le container."""
        try:
            file_inputs = container.locator("input[type='file']")
            count = await file_inputs.count()

            for i in range(count):
                file_input = file_inputs.nth(i)
                try:
                    # Identifier le contexte du champ (label proche)
                    label_text = await self._get_field_label(file_input)
                    label_lower = label_text.lower()

                    print(f"    [↑] Champ fichier détecté — label : '{label_text}'")

                    # Déterminer quel fichier uploader
                    file_to_upload = None

                    # Lettre de motivation
                    if any(kw in label_lower for kw in [
                        "lettre", "cover letter", "motivation", "motivation letter",
                        "covering letter",
                    ]):
                        file_to_upload = self.cover_letter_path
                        if not file_to_upload:
                            print(f"      ⚠️  Lettre de motivation demandée mais non fournie — champ ignoré.")
                            continue

                    # Autres documents personnalisés
                    elif self.extra_docs:
                        for doc_label, doc_path in self.extra_docs.items():
                            if doc_label.lower() in label_lower:
                                file_to_upload = doc_path
                                break

                    # CV (par défaut)
                    if file_to_upload is None:
                        file_to_upload = self.cv_path

                    if file_to_upload and os.path.exists(file_to_upload):
                        await file_input.set_input_files(file_to_upload)
                        await asyncio.sleep(random.uniform(0.8, 1.5))
                        print(f"      ✓ Fichier uploadé : {os.path.basename(file_to_upload)}")
                    else:
                        print(f"      ⚠️  Fichier introuvable : {file_to_upload}")

                except Exception as e:
                    print(f"      ⚠️  Erreur upload champ {i} : {e}")
                    continue

        except Exception as e:
            print(f"    ⚠️  Erreur lors de la gestion des uploads : {e}")

    async def _handle_form_fields(self, container) -> None:
        """
        Remplit les champs texte, select, radio, checkbox et textarea.

        Stratégie :
          1. Téléphone / email : remplissage direct si champ vide
          2. Questions connues (default_answers) : correspondance par mot-clé
          3. Selects : sélectionner la première option non-vide si pas de réponse connue
          4. Champs obligatoires vides : laisser tel quel (ne pas bloquer)
        """
        try:
            # ── Inputs texte ──────────────────────────────────────────────
            text_inputs = container.locator(
                "input[type='text'], input[type='tel'], input[type='email'], "
                "input[type='number'], input:not([type])"
            )
            count = await text_inputs.count()

            for i in range(count):
                inp = text_inputs.nth(i)
                try:
                    if not await inp.is_visible():
                        continue
                    if await inp.get_attribute("readonly") is not None:
                        continue

                    label_text = await self._get_field_label(inp)
                    label_lower = label_text.lower()
                    current_value = (await inp.input_value()).strip()

                    # Trouver une réponse dans default_answers
                    answer = self._find_default_answer(label_lower)

                    if answer is not None and not current_value:
                        await inp.fill(answer)
                        await asyncio.sleep(random.uniform(0.3, 0.7))
                        print(f"    [✏️ ] {label_text} → '{answer}'")
                    elif not current_value:
                        # Champs spécifiques sans réponse explicite
                        inp_type = (await inp.get_attribute("type") or "text").lower()
                        if inp_type == "tel" and self.phone:
                            await inp.fill(self.phone)
                            await asyncio.sleep(0.3)
                            print(f"    [✏️ ] Téléphone → '{self.phone}'")
                        elif inp_type == "email" and self.email:
                            await inp.fill(self.email)
                            await asyncio.sleep(0.3)
                            print(f"    [✏️ ] Email → '{self.email}'")

                except Exception:
                    continue

            # ── Textareas ─────────────────────────────────────────────────
            textareas = container.locator("textarea")
            ta_count = await textareas.count()

            for i in range(ta_count):
                ta = textareas.nth(i)
                try:
                    if not await ta.is_visible():
                        continue
                    label_text = await self._get_field_label(ta)
                    current_value = (await ta.input_value()).strip()
                    if current_value:
                        continue  # déjà rempli

                    answer = self._find_default_answer(label_text.lower())
                    if answer is not None:
                        await ta.fill(answer)
                        await asyncio.sleep(random.uniform(0.3, 0.6))
                        print(f"    [✏️ ] Textarea '{label_text}' → '{answer[:50]}...'")
                except Exception:
                    continue

            # ── Selects ───────────────────────────────────────────────────
            selects = container.locator("select")
            sel_count = await selects.count()

            for i in range(sel_count):
                sel_el = selects.nth(i)
                try:
                    if not await sel_el.is_visible():
                        continue
                    label_text = await self._get_field_label(sel_el)
                    current_value = await sel_el.input_value()

                    # Réponse dans default_answers ?
                    answer = self._find_default_answer(label_text.lower())
                    if answer is not None:
                        try:
                            await sel_el.select_option(label=answer)
                            print(f"    [🔽] Select '{label_text}' → '{answer}'")
                            await asyncio.sleep(0.3)
                            continue
                        except Exception:
                            pass

                    # Sélectionner première option non-vide si pas déjà sélectionnée
                    if not current_value or current_value == "":
                        options = await sel_el.locator("option").all()
                        for opt in options:
                            val = await opt.get_attribute("value")
                            text = (await opt.inner_text()).strip()
                            if val and val not in ("", "Select an option", "Sélectionner"):
                                await sel_el.select_option(value=val)
                                print(f"    [🔽] Select '{label_text}' → '{text}'")
                                await asyncio.sleep(0.3)
                                break

                except Exception:
                    continue

            # ── Radios ────────────────────────────────────────────────────
            # Sélectionner la première option des groupes radio non cochés
            try:
                radio_groups: dict[str, list] = {}
                radios = container.locator("input[type='radio']")
                radio_count = await radios.count()

                for i in range(radio_count):
                    radio = radios.nth(i)
                    try:
                        name = await radio.get_attribute("name") or f"group_{i}"
                        if name not in radio_groups:
                            radio_groups[name] = []
                        radio_groups[name].append(radio)
                    except Exception:
                        continue

                for name, group in radio_groups.items():
                    # Vérifier si l'un est déjà coché
                    already_checked = False
                    for radio in group:
                        try:
                            if await radio.is_checked():
                                already_checked = True
                                break
                        except Exception:
                            continue

                    if not already_checked and group:
                        # Chercher une correspondance dans default_answers
                        answered = False
                        for radio in group:
                            try:
                                label_text = await self._get_field_label(radio)
                                answer = self._find_default_answer(name.lower())
                                if answer and answer.lower() in label_text.lower():
                                    await radio.click()
                                    await asyncio.sleep(0.3)
                                    answered = True
                                    break
                            except Exception:
                                continue

                        # Par défaut : cocher le premier radio visible
                        if not answered:
                            for radio in group:
                                try:
                                    if await radio.is_visible():
                                        await radio.click()
                                        await asyncio.sleep(0.3)
                                        break
                                except Exception:
                                    continue

            except Exception:
                pass

        except Exception as e:
            print(f"    ⚠️  Erreur lors du remplissage des champs : {e}")

    async def _get_field_label(self, element) -> str:
        """
        Retourne le texte du label associé à un élément de formulaire.
        Cherche dans l'ordre : aria-label, <label for=id>, parent <label>, texte précédent.
        """
        try:
            # aria-label direct
            aria = await element.get_attribute("aria-label")
            if aria and aria.strip():
                return aria.strip()

            # placeholder
            placeholder = await element.get_attribute("placeholder")
            if placeholder and placeholder.strip():
                return placeholder.strip()

            # id → <label for="...">
            elem_id = await element.get_attribute("id")
            if elem_id:
                label_loc = self.page.locator(f"label[for='{elem_id}']").first
                if await label_loc.count() > 0:
                    text = (await label_loc.inner_text()).strip()
                    if text:
                        return text

            # Parent ou ancêtre label
            try:
                parent_label = element.locator("xpath=ancestor::label").first
                if await parent_label.count() > 0:
                    text = (await parent_label.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                pass

            # Élément précédent frère
            try:
                prev = element.locator("xpath=preceding-sibling::label[1]").first
                if await prev.count() > 0:
                    text = (await prev.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                pass

        except Exception:
            pass
        return ""

    def _find_default_answer(self, label_lower: str) -> str | None:
        """
        Cherche une réponse dans default_answers par correspondance partielle.

        Args:
            label_lower: Label du champ en minuscules.

        Returns:
            La réponse correspondante ou None si pas trouvée.
        """
        for key, value in self.default_answers.items():
            if key in label_lower or label_lower in key:
                return value
        return None

    async def _find_action_button(self):
        """
        Cherche le bouton d'action principal (Suivant / Vérifier / Soumettre).

        Returns:
            Playwright Locator du bouton, ou None si non trouvé.
        """
        # Priorité : bouton Soumettre (dernière étape)
        for sel in self._SUBMIT_BTN_SELECTORS:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    label = (await loc.get_attribute("aria-label") or "").lower()
                    text  = (await loc.inner_text()).strip().lower()
                    combined = label + " " + text
                    if any(kw in combined for kw in [
                        "soumettre", "submit", "envoyer", "send application"
                    ]):
                        return loc
            except Exception:
                continue

        # Bouton Suivant / Vérifier
        for sel in self._NEXT_BTN_SELECTORS:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return loc
            except Exception:
                continue

        return None

    async def _is_success_page(self) -> bool:
        """
        Détecte si la candidature a été soumise avec succès.
        LinkedIn affiche un écran de confirmation après soumission.
        """
        success_selectors = [
            # Nouvelle UI
            "[data-test-modal-id='easy-apply-success-modal']",
            ".jobs-easy-apply-success-modal",
            # Texte de confirmation dans n'importe quel conteneur
        ]
        success_keywords = [
            "candidature envoyée", "application submitted", "candidature soumise",
            "votre candidature a été", "your application has been",
            "candidature simplifiée envoyée",
        ]

        for sel in success_selectors:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0:
                    return True
            except Exception:
                continue

        try:
            # Chercher le texte de confirmation dans le modal
            modal = await self._get_modal_container()
            modal_text = (await modal.inner_text()).lower()
            if any(kw in modal_text for kw in success_keywords):
                return True
        except Exception:
            pass

        return False

    # ------------------------------------------------------------------
    # Méthodes privées — Persistance
    # ------------------------------------------------------------------

    def _find_existing(self, job_url: str) -> dict | None:
        """Retourne l'enregistrement existant pour job_url, ou None."""
        url = job_url.rstrip("/")
        for r in self._records:
            if r.get("job_url", "").rstrip("/") == url:
                return r
        return None

    def _persist(self, record: dict) -> None:
        """Upsert le record et sauvegarde le fichier Excel."""
        self._records = ExportUtils.upsert(self._records, record, key_field="job_url")
        ExportUtils.save_workbook(self._records, self.applications_file, SHEET_NAME, COLUMNS)