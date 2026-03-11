"""
LinkedInMessenger — sends LinkedIn direct messages via Playwright.
"""
import asyncio
import random


class LinkedInMessenger:
    """
    Sends LinkedIn direct messages programmatically.

    NOTE: Sending messages is only possible when you are connected (1st degree)
    or the recipient accepts InMails. Use responsibly and respect LinkedIn's
    terms of service. The default max_messages limit of 10 helps avoid
    account restrictions.
    """

    def __init__(self, page) -> None:
        self.page = page

    async def _wait_for_profile_load(self) -> None:
        """Attend que la page profil soit bien chargée."""
        try:
            await self.page.wait_for_selector(
                "main, .scaffold-layout__main, section.artdeco-card",
                timeout=15_000,
            )
        except Exception:
            pass
        await asyncio.sleep(random.uniform(1.5, 2.5))

    async def _find_and_click(self, selectors: list[str], timeout: int = 3000) -> bool:
        """
        Parcourt une liste de sélecteurs et clique sur le premier trouvé et visible.
        Les éléments cachés (display:none, visibility:hidden) sont ignorés.
        Retourne True si un clic a été effectué.
        """
        for sel in selectors:
            try:
                all_matches = self.page.locator(sel)
                total = await all_matches.count()
                clicked = False
                for i in range(total):
                    candidate = all_matches.nth(i)
                    is_visible = await candidate.is_visible()
                    if is_visible:
                        await candidate.scroll_into_view_if_needed()
                        await asyncio.sleep(random.uniform(0.3, 0.7))
                        await candidate.click(timeout=timeout)
                        print(f"    [✓] Cliqué sur : {sel} (index {i})")
                        clicked = True
                        break
                if clicked:
                    return True
                elif total > 0:
                    print(f"    [-] {total} élément(s) trouvé(s) mais tous hidden : {sel}")
            except Exception as e:
                print(f"    [✗] Sélecteur échoué ({sel}): {e}")
                continue
        return False

    async def _open_message_window(self) -> bool:
        """
        Tente d'ouvrir la fenêtre de message depuis le profil.
        Stratégie 1 : bouton "Message" dans les actions du profil (header sticky).
        Stratégie 2 : bouton "Plus" → item "Message" dans le dropdown.
        Stratégie 3 : InMail en dernier recours.
        """
        # Scroll en haut de page pour s'assurer que le header sticky est visible
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # --- Stratégie 1 : bouton Message dans les actions du profil uniquement ---
        # On cible UNIQUEMENT les boutons dans .pvs-profile-actions ou le sticky header,
        # pour éviter de cliquer sur le lien "Messagerie" de la nav globale.
        direct_selectors = [
            # Sticky header du profil (2024-2025)
            '.pvs-sticky-header-profile-actions__action[aria-label*="message" i]',
            '.pvs-sticky-header-profile-actions__action[aria-label*="Message"]',
            # Section actions classique sous la photo
            '.pvs-profile-actions button[aria-label*="message" i]',
            '.pvs-profile-actions button[aria-label*="Message"]',
            # Classe spécifique au bouton message du profil
            'button.message-anywhere-button',
            # Bouton avec aria-label contenant le prénom (ex: "Envoyer un message à Luc")
            'button[aria-label^="Envoyer un message"]',
            'button[aria-label^="Send a message"]',
            # Fallback : tous les boutons (PAS les <a>) contenant "Message" dans le texte
            # strictement dans la zone des actions profil
            '.pvs-profile-actions button:has-text("Message")',
            '.pvs-sticky-header-profile-actions button:has-text("Message")',
        ]
        if await self._find_and_click(direct_selectors, timeout=5000):
            return True

        print("    [!] Bouton Message direct non trouvé. Tentative via menu 'Plus'...")

        # --- Stratégie 2 : menu "Plus" dans la section actions ---
        more_selectors = [
            '.pvs-profile-actions button[aria-label*="Plus" i]',
            '.pvs-sticky-header-profile-actions button[aria-label*="Plus" i]',
            '.pvs-profile-actions button[aria-label*="more" i]',
            '.pvs-profile-actions button:has-text("Plus")',
            '.pvs-profile-actions button:has-text("More")',
            'button[id*="overflow"]',
        ]
        clicked_more = await self._find_and_click(more_selectors, timeout=4000)
        if clicked_more:
            await asyncio.sleep(random.uniform(0.8, 1.5))
            dropdown_message_selectors = [
                '.artdeco-dropdown__content li button[aria-label*="message" i]',
                '.artdeco-dropdown__content li button:has-text("Message")',
                '.artdeco-dropdown__content li a:has-text("Message")',
                'div[role="option"]:has-text("Message")',
                'li[role="option"]:has-text("Message")',
            ]
            if await self._find_and_click(dropdown_message_selectors, timeout=4000):
                return True

        print("    [!] Menu Plus non concluant. Tentative InMail...")

        # --- Stratégie 3 : InMail ---
        inmail_selectors = [
            '.pvs-profile-actions button:has-text("InMail")',
            'button[aria-label*="InMail" i]',
            'button:has-text("Envoyer un InMail")',
        ]
        if await self._find_and_click(inmail_selectors, timeout=3000):
            return True

        return False

    async def _fill_message_input(self, message: str) -> bool:
        """
        Attend et remplit la zone de saisie du message.
        Gère la modale de messagerie LinkedIn (fenêtre flottante ou page dédiée).
        """
        await asyncio.sleep(random.uniform(1.0, 2.0))

        input_selectors = [
            # Boîte de message flottante LinkedIn (2024-2025)
            'div.msg-form__contenteditable[contenteditable="true"]',
            'div[data-artdeco-is-focused] div[contenteditable="true"]',
            # Sélecteurs génériques
            'div[role="textbox"][aria-label*="message" i]',
            'div[role="textbox"][aria-label*="Message"]',
            'div[contenteditable="true"][aria-label*="message" i]',
            'div[contenteditable="true"][data-placeholder]',
            'div.msg-form__msg-content-container div[contenteditable="true"]',
            'textarea[name="message"]',
            # Fallback large
            'div[contenteditable="true"]',
        ]

        msg_input = None
        for sel in input_selectors:
            try:
                locator = self.page.locator(sel).first
                await locator.wait_for(state="visible", timeout=6000)
                count = await locator.count()
                if count > 0:
                    msg_input = locator
                    print(f"    [✓] Zone de saisie trouvée : {sel}")
                    break
            except Exception:
                continue

        if msg_input is None:
            print("    [✗] Aucune zone de saisie de message trouvée.")
            return False

        await msg_input.scroll_into_view_if_needed()
        await msg_input.click()
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # Vide le champ au cas où
        await msg_input.press("Control+a")
        await asyncio.sleep(0.2)

        # Saisie humaine caractère par caractère
        await msg_input.type(message, delay=random.randint(25, 60))
        await asyncio.sleep(random.uniform(0.8, 1.5))
        return True

    async def _click_send(self) -> bool:
        """Clique sur le bouton Envoyer dans la fenêtre de message."""
        send_selectors = [
            'button.msg-form__send-button',
            'button[type="submit"].msg-form__send-btn',
            'button[type="submit"]:has-text("Envoyer")',
            'button[type="submit"]:has-text("Send")',
            'button:has-text("Envoyer")',
            'button:has-text("Send")',
            'button[aria-label*="envoyer" i]',
            'button[aria-label*="send" i]',
            # Icône d'envoi (SVG)
            'button.msg-form__send-button[disabled="false"]',
        ]
        sent = await self._find_and_click(send_selectors, timeout=5000)
        if not sent:
            # Dernier recours : Entrée sur la zone de saisie
            print("    [!] Bouton Envoyer non trouvé, tentative via touche Entrée...")
            try:
                await self.page.keyboard.press("Enter")
                sent = True
            except Exception:
                pass
        return sent

    async def send_message(self, profile_url: str, message: str) -> bool:
        """
        Send a direct message to a LinkedIn profile.

        Args:
            profile_url: Full LinkedIn profile URL.
            message:     Text of the message to send.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        try:
            print(f"\n→ Navigation vers : {profile_url}")
            await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=30_000)
            await self._wait_for_profile_load()

            # Étape 1 : Ouvrir la fenêtre de message
            print("  [1] Recherche du bouton Message...")
            opened = await self._open_message_window()
            if not opened:
                print("  [✗] Impossible d'ouvrir la fenêtre de message.")
                # Dump HTML pour diagnostic
                html_snippet = await self.page.evaluate(
                    "() => document.querySelector('.pvs-profile-actions, .scaffold-layout__main')?.innerHTML?.slice(0, 2000) ?? 'non trouvé'"
                )
                print(f"  [DEBUG] HTML actions section:\n{html_snippet[:800]}")
                return False

            # Étape 2 : Remplir le message
            print("  [2] Saisie du message...")
            filled = await self._fill_message_input(message)
            if not filled:
                return False

            # Étape 3 : Envoyer
            print("  [3] Envoi du message...")
            sent = await self._click_send()
            if not sent:
                print("  [✗] Impossible d'envoyer le message.")
                return False

            await asyncio.sleep(random.uniform(1.5, 2.5))
            print("  [✓] Message envoyé avec succès !")
            return True

        except Exception as e:
            print(f"  [✗] Erreur inattendue : {e}")
            return False

    async def send_messages_bulk(
        self,
        contacts: list[dict],
        delay_between: tuple = (5, 15),
        max_messages: int = 10,
    ) -> list[dict]:
        """
        Send messages to multiple contacts with anti-ban delays.

        Args:
            contacts:       List of dicts with keys "profile_url" and "message".
            delay_between:  Tuple of (min_seconds, max_seconds) to wait between
                            messages.
            max_messages:   Safety cap — at most this many messages per session.

        Returns:
            List of result dicts: {"profile_url": str, "success": bool, "error": str}.
        """
        results = []
        targets = contacts[:max_messages]

        for i, contact in enumerate(targets, 1):
            profile_url = contact.get("profile_url", "")
            message = contact.get("message", "")

            if not profile_url or not message:
                results.append({
                    "profile_url": profile_url,
                    "success": False,
                    "error": "Missing profile_url or message",
                })
                continue

            print(f"\n  [{i:2d}/{len(targets)}] → {profile_url}")
            success = False
            error = ""
            try:
                success = await self.send_message(profile_url, message)
            except Exception as e:
                error = str(e)

            results.append({
                "profile_url": profile_url,
                "success": success,
                "error": error,
            })

            if i < len(targets):
                delay = random.uniform(*delay_between)
                print(f"  [⏳] Pause de {delay:.1f}s avant le prochain message...")
                await asyncio.sleep(delay)

        return results
