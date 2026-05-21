# chatbot-service/src/response_formatter.py
"""
Formats structured DB query results into localised natural-language strings.

Improvement: the `language` parameter is now actually used.
Templates are defined for EN, FR, and AR so the formatter produces
correct-language output when the LLM is unavailable or as DB context hints.
"""
from typing import Dict
from datetime import datetime


# ---------------------------------------------------------------------------
# Translation table
# ---------------------------------------------------------------------------
# Each key maps to a dict of {lang_code: string}.
# Add more keys / languages as needed.
# ---------------------------------------------------------------------------
_T = {
    "ticket_header": {
        "en": "You have {n} ticket(s):",
        "fr": "Vous avez {n} billet(s) :",
        "ar": "لديك {n} تذكرة (تذاكر):",
    },
    "status_active":      {"en": "[ACTIVE]",       "fr": "[ACTIF]",       "ar": "[نشط]"},
    "status_used":        {"en": "[USED]",          "fr": "[UTILISÉ]",     "ar": "[مستخدم]"},
    "status_transferred": {"en": "[TRANSFERRED]",   "fr": "[TRANSFÉRÉ]",   "ar": "[محوَّل]"},
    "status_refunded":    {"en": "[REFUNDED]",      "fr": "[REMBOURSÉ]",   "ar": "[مسترد]"},
    "location_label":     {"en": "Venue",           "fr": "Lieu",          "ar": "الملعب"},
    "seat_label":         {"en": "Seat",            "fr": "Siège",         "ar": "المقعد"},
    "zone_label":         {"en": "Zone",            "fr": "Zone",          "ar": "المنطقة"},
    "row_label":          {"en": "Row",             "fr": "Rangée",        "ar": "الصف"},
    "date_label":         {"en": "Date",            "fr": "Date",          "ar": "التاريخ"},
    "kickoff_label":      {"en": "Kick-off",        "fr": "Coup d'envoi",  "ar": "انطلاق المباراة"},
    "status_label":       {"en": "Status",          "fr": "Statut",        "ar": "الحالة"},
    "standard_label":     {"en": "Standard",        "fr": "Standard",      "ar": "عادي"},
    "vip_label":          {"en": "VIP",             "fr": "VIP",           "ar": "VIP"},
    "upcoming_header":    {"en": "Upcoming Matches:","fr": "Prochains matchs :","ar": "المباريات القادمة:"},
    "verified_ok":        {"en": "[VERIFIED] Ticket Verified","fr": "[VÉRIFIÉ] Billet Vérifié","ar": "[موثَّق] التذكرة موثقة"},
    "verified_fail":      {"en": "[FAILED] Verification Failed","fr": "[ÉCHEC] Vérification Échouée","ar": "[فشل] فشل التحقق"},
    "no_tickets":         {"en": "No tickets found.","fr": "Aucun billet trouvé.","ar": "لا توجد تذاكر."},
    "not_found":          {"en": "Not found.",       "fr": "Introuvable.",   "ar": "غير موجود."},
    "authentic":          {"en": "This ticket is authentic and secured by Botola Pro.",
                           "fr": "Ce billet est authentique et sécurisé par Botola Pro.",
                           "ar": "هذه التذكرة أصيلة ومؤمَّنة من Botola Pro."},
    "prices_include":     {"en": "Prices include Botola Pro security verification.",
                           "fr": "Les prix incluent la vérification de sécurité Botola Pro.",
                           "ar": "تشمل الأسعار التحقق الأمني من Botola Pro."},
}


def _t(key: str, lang: str, **kwargs) -> str:
    """Translate a key to the requested language, defaulting to English."""
    translations = _T.get(key, {})
    template = translations.get(lang) or translations.get("en", key)
    return template.format(**kwargs) if kwargs else template


class ResponseFormatter:
    """
    Formats structured data into natural-language responses.
    Supports EN / FR / AR output.
    """

    def format(self, data: Dict, language: str = "en") -> str:
        """Format any data type into a localised response string."""
        # Normalise: map detected ISO codes to our supported set
        lang = self._normalise_lang(language)
        data_type = data.get("type", "unknown")

        formatters = {
            "ticket_list":       self._format_ticket_list,
            "seat_info":         self._format_seat_info,
            "ticket_status":     self._format_ticket_status,
            "match_time":        self._format_match_time,
            "prices":            self._format_prices,
            "price_list":        self._format_price_list,
            "upcoming_matches":  self._format_upcoming,
            "verification":      self._format_verification,
            "transfer_info":     self._format_transfer_info,
            "buy_recommendation":self._format_buy_recommendation,
            "no_tickets":        self._format_no_tickets,
            "not_found":         self._format_not_found,
        }

        formatter = formatters.get(data_type, self._format_generic)
        return formatter(data, lang)

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------

    def _format_ticket_list(self, data: Dict, lang: str) -> str:
        tickets = data.get("tickets", [])
        lines = [_t("ticket_header", lang, n=len(tickets)) + "\n"]
        status_map = {
            "active":      _t("status_active", lang),
            "used":        _t("status_used", lang),
            "transferred": _t("status_transferred", lang),
            "refunded":    _t("status_refunded", lang),
        }
        for t in tickets:
            label = status_map.get(t["status"], f"[{t['status'].upper()}]")
            lines.append(
                f"{label} **{t['home_team']} vs {t['away_team']}**\n"
                f"   {_t('location_label', lang)}: {t['venue']}\n"
                f"   {_t('seat_label', lang)}: {_t('zone_label', lang)} {t['zone']}, "
                f"{_t('row_label', lang)} {t['row']}, #{t['seat_number']}\n"
                f"   {_t('date_label', lang)}: {self._format_date(t['match_date'])} | {t['kickoff_time']}\n"
            )
        return "\n".join(lines)

    def _format_seat_info(self, data: Dict, lang: str) -> str:
        return (
            f"**{data['match']}**\n\n"
            f"{_t('location_label', lang)}: {data['venue']}\n"
            f"{_t('zone_label', lang)}: {data['zone']}\n"
            f"{_t('row_label', lang)}: {data['row']}\n"
            f"{_t('seat_label', lang)}: {data['seat']}\n"
            f"{_t('date_label', lang)}: {self._format_date(data['date'])}"
        )

    def _format_ticket_status(self, data: Dict, lang: str) -> str:
        status_map = {
            "active":      _t("status_active", lang),
            "used":        _t("status_used", lang),
            "transferred": _t("status_transferred", lang),
            "refunded":    _t("status_refunded", lang),
        }
        label = status_map.get(data["status"], f"[{data['status'].upper()}]")
        return (
            f"{label} **Ticket {data['ticket_id']}**\n\n"
            f"{data['match']}\n"
            f"{_t('status_label', lang)}: {data['status'].upper()}\n"
            f"{_t('location_label', lang)}: {data['venue']}\n"
            f"{_t('date_label', lang)}: {self._format_date(data['date'])}"
        )

    def _format_match_time(self, data: Dict, lang: str) -> str:
        return (
            f"**{data['match']}**\n\n"
            f"{_t('date_label', lang)}: {data['date']}\n"
            f"{_t('kickoff_label', lang)}: {data['kickoff']}\n"
            f"{_t('location_label', lang)}: {data['venue']}\n"
            f"{_t('status_label', lang)}: {data['status'].upper()}"
        )

    def _format_prices(self, data: Dict, lang: str) -> str:
        return (
            f"**{data['match']}**\n\n"
            f"{_t('standard_label', lang)}: {data['standard']} MAD\n"
            f"{_t('vip_label', lang)}: {data['vip']} MAD\n\n"
            f"{_t('prices_include', lang)}"
        )

    def _format_price_list(self, data: Dict, lang: str) -> str:
        lines = [_t("upcoming_header", lang) + "\n"]
        for m in data.get("matches", []):
            lines.append(
                f"- **{m['home_team']} vs {m['away_team']}** — "
                f"{_t('standard_label', lang)}: {m['price_standard']} MAD | "
                f"{_t('vip_label', lang)}: {m['price_vip']} MAD"
            )
        return "\n".join(lines)

    def _format_upcoming(self, data: Dict, lang: str) -> str:
        lines = [_t("upcoming_header", lang) + "\n"]
        for m in data.get("matches", []):
            lines.append(
                f"- **{m['home_team']} vs {m['away_team']}**\n"
                f"  {_t('location_label', lang)}: {m['venue']} | "
                f"{_t('kickoff_label', lang)}: {m['kickoff_time']}"
            )
        return "\n".join(lines)

    def _format_verification(self, data: Dict, lang: str) -> str:
        if data.get("verified"):
            return (
                f"{_t('verified_ok', lang)}\n\n"
                f"Ticket ID: {data['ticket_id']}\n"
                f"{data['match']}\n"
                f"Hash: `{data['blockchain_hash']}`\n\n"
                f"{_t('authentic', lang)}"
            )
        return f"{_t('verified_fail', lang)}: {data.get('reason', 'Unknown error')}"

    def _format_transfer_info(self, data: Dict, lang: str) -> str:
        if data.get("error"):
            return data["error"]
        transferable = data.get("transferable", False)
        state = "✅ Transferable" if transferable else "❌ Not transferable"
        return (
            f"**Ticket {data.get('ticket_id')}** — {data.get('match')}\n"
            f"{state}\n"
            f"{data.get('action_required', '')}"
        )

    def _format_buy_recommendation(self, data: Dict, lang: str) -> str:
        lines = [_t("upcoming_header", lang) + "\n"]
        for m in data.get("matches", []):
            lines.append(
                f"- **{m['home_team']} vs {m['away_team']}** @ {m['venue']}\n"
                f"  {_t('kickoff_label', lang)}: {m['kickoff_time']} | "
                f"{_t('standard_label', lang)}: {m.get('price_standard', '?')} MAD"
            )
        return "\n".join(lines)

    def _format_no_tickets(self, data: Dict, lang: str) -> str:
        return data.get("message") or _t("no_tickets", lang)

    def _format_not_found(self, data: Dict, lang: str) -> str:
        return data.get("message") or _t("not_found", lang)

    def _format_generic(self, data: Dict, lang: str) -> str:
        return str(data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_lang(lang: str) -> str:
        """Map detected language codes to our supported set (en/fr/ar)."""
        lang = (lang or "en").lower()
        if lang.startswith("ar"):
            return "ar"
        if lang.startswith("fr"):
            return "fr"
        return "en"  # default

    @staticmethod
    def _format_date(date_val) -> str:
        if isinstance(date_val, str):
            return date_val
        if hasattr(date_val, "strftime"):
            return date_val.strftime("%B %d, %Y at %H:%M")
        return str(date_val)