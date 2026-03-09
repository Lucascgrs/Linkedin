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
            await self.page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1, 3))

            # Click the "Message" button
            message_btn_selectors = [
                'button:has-text("Message")',
                'button:has-text("Envoyer un message")',
                '.pvs-profile-actions button[aria-label*="message" i]',
                'a:has-text("Message")',
            ]
            clicked = False
            for sel in message_btn_selectors:
                btn = self.page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    clicked = True
                    break

            if not clicked:
                print(f"  ⚠️ Bouton Message non trouvé sur {profile_url}")
                return False

            await asyncio.sleep(random.uniform(1, 2))

            # Wait for the message input to appear
            input_selectors = [
                'div[role="textbox"][aria-label*="message" i]',
                'div[contenteditable="true"]',
                'textarea[name="message"]',
            ]
            msg_input = None
            for sel in input_selectors:
                elem = self.page.locator(sel).first
                if await elem.count() > 0:
                    msg_input = elem
                    break

            if msg_input is None:
                print(f"  ⚠️ Zone de saisie non trouvée sur {profile_url}")
                return False

            await msg_input.click()
            await asyncio.sleep(random.uniform(0.5, 1))

            # Type message character by character for a human-like feel
            await msg_input.type(message, delay=30)
            await asyncio.sleep(random.uniform(1, 2))

            # Send the message
            send_btn_selectors = [
                'button[type="submit"]:has-text("Envoyer")',
                'button[type="submit"]:has-text("Send")',
                'button:has-text("Envoyer")',
                'button:has-text("Send")',
                'button[aria-label*="envoyer" i]',
                'button[aria-label*="send" i]',
            ]
            sent = False
            for sel in send_btn_selectors:
                btn = self.page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    sent = True
                    break

            if not sent:
                print(f"  ⚠️ Bouton Envoyer non trouvé pour {profile_url}")
                return False

            await asyncio.sleep(random.uniform(1, 2))
            return True

        except Exception as e:
            print(f"  ⚠️ Erreur lors de l'envoi du message à {profile_url}: {e}")
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

            print(f"  [{i:2d}/{len(targets)}] → {profile_url}")
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
                print(f"         ⏳ Pause {delay:.1f}s avant le prochain message…")
                await asyncio.sleep(delay)

        return results
