"""Server-side strings in both official languages.

The API speaks English by default. Callers pass ``locale`` (``en`` | ``fr``) and every string the API *generates*
(resource-type labels, facet labels, metadata summaries, guide abstain messages, connector access notes) comes from
here. Source data (titles, descriptions, partner-typed notes) is never translated — it stays in its source language.
"""
from __future__ import annotations

import re
from typing import Any

LOCALES = ("en", "fr")
DEFAULT_LOCALE = "en"


def norm_locale(value: str | None) -> str:
    v = (value or "").strip().lower()[:2]
    return v if v in LOCALES else DEFAULT_LOCALE


TYPE_LABEL: dict[str, dict[str, str]] = {
    "en": {
        "book": "Book", "serial": "Serial / periodical", "manuscript": "Manuscript", "archival_collection": "Archival collection",
        "image": "Image", "map": "Map", "audio": "Audio", "video": "Video", "dataset": "Dataset", "finding_aid": "Finding aid",
        "artifact": "Artifact / object", "other": "Other",
    },
    "fr": {
        "book": "Livre", "serial": "Périodique", "manuscript": "Manuscrit", "archival_collection": "Fonds d'archives",
        "image": "Image", "map": "Carte", "audio": "Audio", "video": "Vidéo", "dataset": "Jeu de données", "finding_aid": "Instrument de recherche",
        "artifact": "Artefact / objet", "other": "Autre",
    },
}

# ISO 639-1/-2 codes stored on records → display names. ``zxx`` is the ISO code for "no linguistic content"
# (maps, photographs, objects); ``und`` undetermined; ``mul`` several languages.
LANGUAGE_NAME: dict[str, dict[str, str]] = {
    "en": {
        "en": "English", "fr": "French", "zxx": "No linguistic content", "und": "Undetermined", "mul": "Multiple languages",
        "es": "Spanish", "de": "German", "pt": "Portuguese", "it": "Italian", "la": "Latin", "nl": "Dutch", "ar": "Arabic",
        "mic": "Mi'kmaq", "gd": "Scottish Gaelic", "yo": "Yoruba", "sw": "Swahili", "ht": "Haitian Creole",
    },
    "fr": {
        "en": "Anglais", "fr": "Français", "zxx": "Sans contenu linguistique", "und": "Indéterminée", "mul": "Plusieurs langues",
        "es": "Espagnol", "de": "Allemand", "pt": "Portugais", "it": "Italien", "la": "Latin", "nl": "Néerlandais", "ar": "Arabe",
        "mic": "Mi'kmaq", "gd": "Gaélique écossais", "yo": "Yoruba", "sw": "Swahili", "ht": "Créole haïtien",
    },
}

ACCESS_LABEL: dict[str, dict[str, str]] = {
    "en": {"online": "Online", "physical": "Physical", "both": "Online + physical", "unknown": "Access unknown"},
    "fr": {"online": "En ligne", "physical": "Sur place", "both": "En ligne + sur place", "unknown": "Accès inconnu"},
}

RIGHTS_LABEL: dict[str, dict[str, str]] = {
    "en": {"public_domain": "Public domain", "open_licence": "Open licence", "in_copyright": "In copyright", "unknown": "Rights unknown", "restricted": "Restricted"},
    "fr": {"public_domain": "Domaine public", "open_licence": "Licence ouverte", "in_copyright": "Sous droit d'auteur", "unknown": "Droits inconnus", "restricted": "Accès restreint"},
}

VERIFICATION_LABEL: dict[str, dict[str, str]] = {
    "en": {
        "verified_partner": "Partner-verified holding", "catalogue_record": "Catalogue record", "unverified": "Unverified holding",
        "demo": "Demo / sample data", "online_item": "Online item (not a physical holding)",
    },
    "fr": {
        "verified_partner": "Fonds vérifié par le partenaire", "catalogue_record": "Notice de catalogue", "unverified": "Fonds non vérifié",
        "demo": "Données de démonstration", "online_item": "Document en ligne (pas un fonds physique)",
    },
}

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "guide.no_evidence": "No records in the index match this question, so there is nothing to cite.",
        "guide.not_configured": "AI guide not configured ({error}). Showing the matching records instead.",
        "guide.validation_failed": "The guide could not produce an answer whose citations all resolve to retrieved records, so it abstains. The matching records are listed below.",
        "guide.insufficient": "Insufficient evidence.",
        "guide.daily_limit": "Nova has answered as many questions as she can today. Here are the matching records; written answers come back tomorrow.",
        "summary.by": "by",
        "summary.subjects": "Subjects:",
        "institution.unknown": "holding institution unknown",
    },
    "fr": {
        "guide.no_evidence": "Aucune notice de l'index ne correspond à cette question; il n'y a donc rien à citer.",
        "guide.not_configured": "Le guide IA n'est pas configuré ({error}). Voici plutôt les notices correspondantes.",
        "guide.validation_failed": "Le guide n'a pas pu produire une réponse dont toutes les citations renvoient à des notices trouvées; il s'abstient donc. Les notices correspondantes sont listées ci-dessous.",
        "guide.insufficient": "Preuves insuffisantes.",
        "guide.daily_limit": "Nova a répondu à autant de questions que possible aujourd'hui. Voici les notices correspondantes; les réponses rédigées reviennent demain.",
        "summary.by": "par",
        "summary.subjects": "Sujets :",
        "institution.unknown": "institution de conservation inconnue",
    },
}


def t(locale: str, key: str, **kw: Any) -> str:
    loc = norm_locale(locale)
    s = MESSAGES.get(loc, {}).get(key) or MESSAGES["en"].get(key) or key
    return s.format(**kw) if kw else s


def type_label(resource_type: str, locale: str = "en") -> str:
    loc = norm_locale(locale)
    return TYPE_LABEL[loc].get(resource_type) or TYPE_LABEL["en"].get(resource_type) or resource_type


def language_name(code: str, locale: str = "en") -> str:
    """Display name for a stored language code. Tolerates un-normalised values ("Eng", "fre") via lang_code()."""
    from app.services.normalize import lang_code  # local import: normalize has no i18n dependency

    loc = norm_locale(locale)
    c = (lang_code(code) or code or "").lower()
    return LANGUAGE_NAME[loc].get(c) or LANGUAGE_NAME["en"].get(c) or code


# ---------------------------------------------------------------------------------------------------- access notes
# Connector access notes are generated English sentences (see app/adapters/*). They are translated sentence by
# sentence; a sentence we do not recognise (e.g. a partner's own text) is kept as written.
_EXACT_FR: dict[str, str] = {
    "Held by the Library of Congress (Washington, DC). Use the catalogue record to request the item in a reading room.":
        "Conservé par la Library of Congress (Washington, DC). Utilisez la notice de catalogue pour demander le document en salle de lecture.",
    "A digital version is linked from the record.": "Une version numérique est liée à la notice.",
    "Library of Congress digital collections item; see the item page for rights and access.":
        "Document des collections numériques de la Library of Congress; consultez la page du document pour les droits et l'accès.",
    "Lending-library item on archive.org: borrow with a free Internet Archive account (controlled digital lending).":
        "Document de la bibliothèque de prêt d'archive.org : empruntez-le avec un compte Internet Archive gratuit (prêt numérique contrôlé).",
    "Open online on archive.org.": "En libre accès en ligne sur archive.org.",
    "Held by The National Archives (Kew, UK). Order the document to a reading room or request a digital copy via the catalogue entry.":
        "Conservé par The National Archives (Kew, Royaume-Uni). Commandez le document en salle de lecture ou demandez une copie numérique à partir de la notice.",
    "Media file hosted on Wikimedia Commons; the licence shown comes from the file's structured metadata. Not a museum or archive holding.":
        "Fichier média hébergé sur Wikimedia Commons; la licence affichée provient des métadonnées structurées du fichier. Il ne s'agit pas d'un fonds de musée ou d'archives.",
    "Catalogued by Harvard Library; see the HOLLIS record for the holding repository.":
        "Catalogué par la Harvard Library; consultez la notice HOLLIS pour connaître le dépôt qui le conserve.",
    "The catalogue describes an online resource licensed to Harvard; access may require Harvard credentials.":
        "Le catalogue décrit une ressource en ligne sous licence Harvard; l'accès peut exiger des identifiants Harvard.",
    "Open government dataset on data.novascotia.ca (download as CSV/JSON). Not an archival holding.":
        "Jeu de données ouvertes sur data.novascotia.ca (téléchargement en CSV/JSON). Il ne s'agit pas d'un fonds d'archives.",
    "Catalogue record from Smithsonian Open Access.": "Notice de catalogue tirée de Smithsonian Open Access.",
    "Online media available.": "Média en ligne disponible.",
    "Digitised item held by The New York Public Library (Schomburg Center and other divisions); the original is consulted on site, the digital copy online.":
        "Document numérisé conservé par The New York Public Library (Schomburg Center et autres divisions); l'original se consulte sur place, la copie numérique en ligne.",
    "Digital item aggregated by Europeana.": "Document numérique agrégé par Europeana.",
    "Digital item aggregated by DPLA.": "Document numérique agrégé par DPLA.",
    "Held by Dalhousie University Archives (Killam Memorial Library, Halifax). The finding aid is online; the material is consulted in the reading room by appointment.":
        "Conservé par les Dalhousie University Archives (Killam Memorial Library, Halifax). L'instrument de recherche est en ligne; les documents se consultent en salle de lecture sur rendez-vous.",
    "Finding aid uploaded by the holding institution. Contact the institution to consult the described material.":
        "Instrument de recherche téléversé par l'institution qui conserve le fonds. Communiquez avec elle pour consulter les documents décrits.",
}
_PATTERN_FR: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^Digitized from the collection of (.+?) \(shown as provenance, not as a verified current holding\)\.$"),
     r"Numérisé à partir de la collection de \1 (indiqué comme provenance, non comme fonds actuel vérifié)."),
    (re.compile(r"^The catalogue marks this record as not open \(closure status (.+?)\)\.$"),
     r"Le catalogue indique que ce document n'est pas ouvert (statut de fermeture \1)."),
    (re.compile(r"^Held by (.+?) \(Harvard University\)\.$"), r"Conservé par \1 (Harvard University)."),
    (re.compile(r"^Held by the (.+?) \(Smithsonian Institution\)\.$"), r"Conservé par \1 (Smithsonian Institution)."),
    (re.compile(r"^Digital item aggregated by Europeana from (.+?)\.$"), r"Document numérique agrégé par Europeana à partir de \1."),
    (re.compile(r"^Digital item aggregated by DPLA from (.+?)\.$"), r"Document numérique agrégé par DPLA à partir de \1."),
    (re.compile(r"^Held physically by (.+?)\.$"), r"Conservé physiquement par \1."),
]
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _explode(table: dict[str, str]) -> dict[str, str]:
    """Multi-sentence entries are also registered sentence by sentence, since notes are translated per sentence."""
    out = dict(table)
    for en, fr in table.items():
        en_parts, fr_parts = _SENTENCE_SPLIT.split(en), _SENTENCE_SPLIT.split(fr)
        if len(en_parts) == len(fr_parts) > 1:
            out.update(zip(en_parts, fr_parts, strict=True))
    return out


_EXACT_FR = _explode(_EXACT_FR)


def _translate_sentence_fr(sentence: str) -> str:
    s = sentence.strip()
    if s in _EXACT_FR:
        return _EXACT_FR[s]
    for pat, repl in _PATTERN_FR:
        if pat.match(s):
            return pat.sub(repl, s)
    return s  # unknown (partner-written) text stays in its source language


def localize_access_note(note: str | None, locale: str = "en") -> str | None:
    if not note or norm_locale(locale) != "fr":
        return note
    # Some generated notes glue two sentences without a capital after the period (none today), so split on ". X".
    return " ".join(_translate_sentence_fr(p) for p in _SENTENCE_SPLIT.split(note.strip()))
