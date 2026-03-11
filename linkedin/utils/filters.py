"""
Reference dictionaries and filter resolution utilities used by all search classes.
"""
from typing import Optional


# ============================================================
# 🗺️  GEO IDs (LinkedIn location codes)
# ============================================================

GEO_IDS: dict[str, str] = {
    # Europe
    "france":               "105015875",
    "belgique":             "100565514",
    "suisse":               "106693272",
    "luxembourg":           "104042105",
    "allemagne":            "101282230",
    "autriche":             "103883259",
    "espagne":              "105646813",
    "italie":               "103350119",
    "portugal":             "105294751",
    "pays-bas":             "104514075",
    "suede":                "105117694",
    "norvege":              "103819153",
    "danemark":             "104514162",
    "finlande":             "100456013",
    "pologne":              "105072130",
    "republique-tcheque":   "104508036",
    "hongrie":              "100288700",
    "roumanie":             "106670623",
    "grece":                "104677530",
    "royaume-uni":          "101165590",
    "irlande":              "104738515",
    # Amérique du Nord
    "etats-unis":           "103644278",
    "canada":               "101174742",
    "mexique":              "103323778",
    # Amérique du Sud
    "bresil":               "106057199",
    "argentine":            "100446943",
    # Asie
    "japon":                "101355337",
    "chine":                "102890883",
    "inde":                 "102713980",
    "coree-du-sud":         "105149290",
    "singapour":            "102454443",
    "emirats-arabes-unis":  "104305776",
    # Océanie
    "australie":            "101452733",
    "nouvelle-zelande":     "105490917",
    # Afrique
    "maroc":                "102047416",
    "tunisie":              "104278506",
    "afrique-du-sud":       "104035573",
}

# ============================================================
# 🏭  INDUSTRY IDs
# ============================================================

INDUSTRY_IDS: dict[str, str] = {
    "software":                 "4",
    "informatique":             "4",
    "it":                       "4",
    "hardware":                 "48",
    "semiconducteurs":          "49",
    "internet":                 "6",
    "telecom":                  "8",
    "jeux-video":               "41",
    "intelligence-artificielle":"1810",
    "finance":                  "43",
    "banque":                   "41",
    "assurance":                "42",
    "capital-risque":           "44",
    "comptabilite":             "50",
    "conseil":                  "96",
    "consulting":               "96",
    "management":               "96",
    "sante":                    "14",
    "medecine":                 "14",
    "pharma":                   "15",
    "biotechnologie":           "16",
    "industrie":                "22",
    "automobile":               "23",
    "aeronautique":             "24",
    "energie":                  "30",
    "marketing":                "80",
    "publicite":                "80",
    "rh":                       "97",
    "recrutement":              "137",
    "juridique":                "74",
    "immobilier":               "44",
    "logistique":               "78",
    "transport":                "77",
    "education":                "69",
    "media":                    "36",
    "presse":                   "36",
    "ecommerce":                "27",
    "retail":                   "27",
    "restauration":             "9",
    "tourisme":                 "53",
    "luxe":                     "60",
    "mode":                     "60",
    "ong":                      "94",
    "association":              "94",
    "gouvernement":             "76",
    "administration":           "76",
}

# ============================================================
# 🏢  COMPANY SIZE codes
# ============================================================

COMPANY_SIZE_IDS: dict[str, str] = {
    "1-10":       "A",
    "11-50":      "B",
    "51-200":     "C",
    "201-500":    "D",
    "501-1000":   "E",
    "1001-5000":  "F",
    "5001-10000": "G",
    "10001+":     "H",
}

# ============================================================
# 📅  DATE POSTED codes (f_TPR)
# ============================================================

DATE_POSTED: dict[str, str] = {
    "24h":      "r86400",
    "semaine":  "r604800",
    "mois":     "r2592000",
}

# ============================================================
# 🏠  WORKPLACE TYPE codes (f_WT)
# ============================================================

WORKPLACE_TYPE: dict[str, str] = {
    "presentiel":   "1",
    "sur-site":     "1",
    "on-site":      "1",
    "hybride":      "2",
    "hybrid":       "2",
    "remote":       "3",
    "teletravail":  "3",
    "distanciel":   "3",
}

# ============================================================
# 💼  JOB TYPE codes (f_JT)
# ============================================================

JOB_TYPE: dict[str, str] = {
    "cdi":          "F",
    "full-time":    "F",
    "temps-plein":  "F",
    "cdd":          "C",
    "contract":     "C",
    "contrat":      "C",
    "temps-partiel":"P",
    "part-time":    "P",
    "stage":        "I",
    "internship":   "I",
    "interim":      "T",
    "temporary":    "T",
    "benevole":     "V",
    "volunteer":    "V",
}

# ============================================================
# 🎓  EXPERIENCE LEVEL codes (f_E)
# ============================================================

EXPERIENCE_LEVEL: dict[str, str] = {
    "stage":            "1",
    "internship":       "1",
    "debutant":         "2",
    "junior":           "2",
    "entry":            "2",
    "entry-level":      "2",
    "associe":          "3",
    "associate":        "3",
    "confirme":         "4",
    "senior":           "4",
    "mid-senior":       "4",
    "manager":          "4",
    "directeur":        "5",
    "director":         "5",
    "executif":         "6",
    "executive":        "6",
    "vp":               "6",
}


# ============================================================
# 🔧  HELPER FUNCTIONS
# ============================================================

def normalize(s: str) -> str:
    """Normalize a string: lowercase, hyphens, no accents."""
    return (
        s.strip().lower()
        .replace(" ", "-")
        .replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
        .replace("à", "a").replace("â", "a").replace("ä", "a")
        .replace("ô", "o").replace("ö", "o")
        .replace("ù", "u").replace("û", "u").replace("ü", "u")
        .replace("î", "i").replace("ï", "i")
        .replace("ç", "c").replace("œ", "oe").replace("æ", "ae")
    )


def resolve_filter(value: str, mapping: dict, filter_name: str) -> Optional[str]:
    """
    Resolve a human-readable name to its LinkedIn ID.

    Supports exact matches (after normalization), raw numeric IDs, and
    partial substring matches. Prints a warning when the value is
    ambiguous or unrecognized.

    Args:
        value:       Human-readable filter value (e.g. "france", "software").
        mapping:     Reference dictionary mapping normalized names to IDs.
        filter_name: Display name used in warning messages (e.g. "pays").

    Returns:
        The corresponding LinkedIn ID string, or None if not found.
    """
    if not value:
        return None

    key = normalize(value)

    if key in mapping:
        return mapping[key]

    if value.strip().isdigit():
        return value.strip()

    matches = [(k, v) for k, v in mapping.items() if key in k or k in key]
    if len(matches) == 1:
        return matches[0][1]
    elif len(matches) > 1:
        return matches[0][1]

    return None


def resolve_multi(values: list, mapping: dict, filter_name: str) -> list:
    """
    Resolve a list of human-readable values to their LinkedIn IDs.

    Applies :func:`resolve_filter` to each element and silently drops
    values that cannot be resolved.

    Args:
        values:      List of human-readable filter values.
        mapping:     Reference dictionary mapping normalized names to IDs.
        filter_name: Display name used in warning messages.

    Returns:
        List of resolved LinkedIn ID strings (unresolvable items omitted).
    """
    return [r for v in values if (r := resolve_filter(v, mapping, filter_name)) is not None]
