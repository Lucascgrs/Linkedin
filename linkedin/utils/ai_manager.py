"""
AIManager — interface Claude (Anthropic) pour améliorer les lettres de motivation.

Fonctionnalités :
  - generate_response(system_prompt, user_messages) : appel générique à l'API Claude
  - improve_cover_letter(...)                       : améliore une lettre de motivation
    en tenant compte du poste, de l'entreprise et du profil du candidat

Usage :
    import os
    from linkedin.utils.ai_manager import AIManager

    ai = AIManager(api_key=os.getenv("ANTHROPIC_API_KEY"))

    improved = ai.improve_cover_letter(
        cover_letter_content=original_text,
        company_info={
            "name": "Acme Corp",
            "sector": "SaaS",
            "job_title": "Data Scientist",
            "job_description": "...",
        },
        personal_info={
            "name": "Lucas Congras",
            "degree": "MSc Data Science",
            "skills": "Python, ML, SQL",
            "experiences": "Stage data analyst 6 mois, alternance 1 an",
        },
        instructions="Rendre la lettre plus concise et mettre en avant Python.",
    )
"""
import logging
import os

logger = logging.getLogger(__name__)


class AIManager:
    """
    Wrapper autour de l'API Claude (Anthropic) pour les tâches de génération de texte.

    Usage principal : améliorer des lettres de motivation en fournissant le contexte
    du poste et les informations du candidat au modèle.

    Args:
        api_key:    Clé API Anthropic. Si vide, lit la variable d'environnement
                    ``ANTHROPIC_API_KEY``. Lève ValueError si aucune clé n'est trouvée.
        model:      Identifiant du modèle Claude. Par défaut "claude-sonnet-4-6".
        max_tokens: Nombre maximum de tokens dans la réponse. Par défaut 2048.

    Raises:
        ImportError: Si le package ``anthropic`` n'est pas installé.
        ValueError:  Si aucune clé API n'est disponible.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
    ) -> None:
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError(
                "Le package anthropic est requis pour AIManager. "
                "Installez-le avec : pip install anthropic"
            ) from exc

        # Résolution de la clé API
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "Aucune clé API Anthropic fournie. "
                "Passez-la au constructeur ou définissez la variable d'environnement ANTHROPIC_API_KEY."
            )

        self.model = model
        self.max_tokens = max_tokens
        self._client = _anthropic.Anthropic(api_key=resolved_key)
        logger.debug("AIManager initialisé avec le modèle %s", model)

    # ──────────────────────────────────────────────────────────────
    # Méthodes publiques
    # ──────────────────────────────────────────────────────────────

    def generate_response(
        self,
        system_prompt: str,
        user_messages: list[str],
    ) -> str:
        """
        Appel générique à l'API Claude.

        Les messages utilisateur sont concaténés avec double saut de ligne avant envoi.

        Args:
            system_prompt:  Instruction donnée au modèle en tant que rôle système.
            user_messages:  Un ou plusieurs blocs de texte formant le tour utilisateur.
                            Ils sont joints avec "\\n\\n" avant l'envoi.

        Returns:
            Réponse textuelle du modèle (stripped).

        Raises:
            anthropic.APIError: Propagée telle quelle en cas d'échec de l'API.
        """
        combined_user = "\n\n".join(user_messages)
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": combined_user}],
        )
        return message.content[0].text.strip()

    def improve_cover_letter(
        self,
        cover_letter_content: str,
        company_info: dict,
        personal_info: dict,
        instructions: str = "",
    ) -> str:
        """
        Améliore une lettre de motivation en tenant compte du poste et de l'entreprise.

        Construit un prompt structuré et appelle ``generate_response`` en interne.

        Règles appliquées au modèle :
          - Conserver la même langue que la lettre originale.
          - Ne pas inventer de faits sur le candidat.
          - Retourner UNIQUEMENT le texte de la lettre améliorée (sans préambule).
          - Maintenir un ton formel adapté à une candidature professionnelle.

        Args:
            cover_letter_content: Texte complet de la lettre de motivation originale.
            company_info:         Informations sur l'entreprise et le poste.
                                  Clés reconnues : "name", "sector", "job_title", "job_description".
                                  Les clés absentes sont remplacées par "N/A".
            personal_info:        Informations sur le candidat.
                                  Clés reconnues : "name", "degree", "skills", "experiences".
                                  Les clés absentes sont remplacées par "N/A".
            instructions:         Instructions supplémentaires optionnelles pour le modèle
                                  (ex. "Mettre en avant Python", "Réduire à 3 paragraphes").

        Returns:
            Texte de la lettre de motivation améliorée.
        """
        system_prompt = (
            "You are an expert career coach specialising in writing compelling cover letters.\n"
            "Your task is to rewrite the provided cover letter to better match the target "
            "position and company. Follow these rules strictly:\n"
            "1. Keep the SAME language as the original letter (French if French, English if English).\n"
            "2. Do NOT invent any facts about the candidate.\n"
            "3. Return ONLY the improved letter text — no explanation, no preamble, no commentary.\n"
            "4. Preserve the formal tone appropriate for a professional job application."
        )

        user_content = (
            "## Lettre de motivation originale\n"
            f"{cover_letter_content}\n\n"

            "## Poste ciblé\n"
            f"Intitulé du poste : {company_info.get('job_title', 'N/A')}\n"
            f"Entreprise        : {company_info.get('name', 'N/A')}\n"
            f"Secteur           : {company_info.get('sector', 'N/A')}\n"
            f"Description       : {company_info.get('job_description', 'N/A')}\n\n"

            "## Profil du candidat\n"
            f"Nom               : {personal_info.get('name', 'N/A')}\n"
            f"Formation         : {personal_info.get('degree', 'N/A')}\n"
            f"Compétences       : {personal_info.get('skills', 'N/A')}\n"
            f"Expériences       : {personal_info.get('experiences', 'N/A')}\n\n"

            "## Instructions supplémentaires\n"
            f"{instructions if instructions else 'Aucune instruction supplémentaire.'}\n\n"

            "Réécris maintenant la lettre de motivation :"
        )

        logger.debug(
            "improve_cover_letter : poste=%s entreprise=%s",
            company_info.get("job_title"),
            company_info.get("name"),
        )
        return self.generate_response(system_prompt, [user_content])
