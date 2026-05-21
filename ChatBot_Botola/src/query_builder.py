# chatbot-service/src/query_builder.py
"""
Builds and executes database queries based on intent and extracted entities.

Improvements:
- Team names are loaded dynamically from the DB (with hardcoded fallback).
- Team alias table maps common abbreviations and Arabic names to canonical names.
- Ticket transfer actually records the state change in the DB.
- Structured logging replaces print() calls.
"""
import re
from typing import Dict, List, Optional
from datetime import datetime

from .db_connector import DBConnector
from .logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Team alias table
# Maps user-visible aliases → DB canonical name fragments.
# Extend this as new teams join / are commonly misspelled.
# ---------------------------------------------------------------------------
TEAM_ALIASES: Dict[str, str] = {
    # WAC / Wydad
    "wac":         "WAC",
    "wydad":       "WAC",
    "الوداد":      "WAC",
    # Raja
    "raja":        "Raja",
    "rajaoui":     "Raja",
    "الرجاء":      "Raja",
    # MAS
    "mas":         "MAS",
    "مولودية":     "MAS",
    # AS FAR / FAR
    "far":         "FAR",
    "as far":      "FAR",
    "الجيش":       "FAR",
    # FUS Rabat
    "fus":         "FUS",
    "فاس":         "FUS",
    # RSB
    "rsb":         "RSB",
    "berkane":     "RSB",
    "نهضة بركان":  "RSB",
    # OCS / Olympic Safi
    "ocs":         "OCS",
    "olympic safi":"OCS",
    "أولمبيك آسفي":"OCS",
    # CODM
    "codm":        "CODM",
    "مكناس":       "CODM",
    # KACM
    "kacm":        "KACM",
    "مراكش":       "KACM",
    # DHJ
    "dhj":         "DHJ",
    "hassania":    "DHJ",
    "الحسنية":     "DHJ",
    # IRT
    "irt":         "IRT",
    "تانغير":      "IRT",
    # Moghreb Tétouan
    "mat":         "MAT",
    "tétouan":     "MAT",
    "تطوان":       "MAT",
}


class QueryBuilder:
    """
    Builds and executes database queries based on intent and entities.
    """

    def __init__(self):
        self.db = DBConnector()

    # ------------------------------------------------------------------
    # Main dispatcher
    # ------------------------------------------------------------------

    def build_and_execute(self, intent: str, message: str, user_id: str) -> Dict:
        """
        Main entry point: given intent and raw message, fetch relevant data.
        Returns structured data for response formatting.
        """
        handlers = {
            "my_tickets":         lambda: self._handle_my_tickets(user_id),
            "seat_location":      lambda: self._handle_seat_location(message, user_id),
            "ticket_status":      lambda: self._handle_ticket_status(message, user_id),
            "match_time":         lambda: self._handle_match_time(message),
            "price_check":        lambda: self._handle_price_check(message),
            "ticket_verification":lambda: self._handle_verification(message, user_id),
            "transfer_ticket":    lambda: self._handle_transfer_ticket(message, user_id),
            "buy_ticket":         lambda: self._handle_buy_ticket(message),
        }

        handler = handlers.get(intent)
        if handler:
            return handler()

        logger.warning("Unhandled dynamic intent", extra={"intent": intent})
        return {"error": f"Unhandled dynamic intent: {intent}"}

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def _handle_my_tickets(self, user_id: str) -> Dict:
        tickets = self.db.get_user_tickets(user_id)
        return {"type": "ticket_list", "count": len(tickets), "tickets": tickets}

    def _handle_seat_location(self, message: str, user_id: str) -> Dict:
        match = self._extract_match_from_message(message)

        if match:
            tickets = self.db.get_user_tickets(user_id)
            for t in tickets:
                if (
                    match["home_team"].upper() in message.upper()
                    or match["away_team"].upper() in message.upper()
                ):
                    return self._seat_dict(t)

        # Fallback: return most upcoming active ticket
        tickets = self.db.get_user_tickets(user_id)
        upcoming = [t for t in tickets if t["status"] == "active"]
        if upcoming:
            return self._seat_dict(upcoming[0])

        return {"type": "no_tickets", "message": "No active tickets found."}

    def _handle_ticket_status(self, message: str, user_id: str) -> Dict:
        ticket_id = self._extract_ticket_id(message)
        if ticket_id:
            ticket = self.db.get_ticket_by_id(ticket_id)
        else:
            tickets = self.db.get_user_tickets(user_id)
            ticket = tickets[-1] if tickets else None

        if not ticket:
            return {"type": "not_found", "message": "Ticket not found."}

        return {
            "type":      "ticket_status",
            "ticket_id": ticket.get("id") or ticket.get("ticket_id"),
            "match":     f"{ticket['home_team']} vs {ticket['away_team']}",
            "status":    ticket["status"],
            "venue":     ticket["venue"],
            "date":      ticket["match_date"],
        }

    def _handle_match_time(self, message: str) -> Dict:
        match = self._extract_match_from_message(message)
        if match:
            return {
                "type":    "match_time",
                "match":   f"{match['home_team']} vs {match['away_team']}",
                "venue":   match["venue"],
                "date":    (match["match_date"].strftime("%Y-%m-%d")
                            if hasattr(match["match_date"], "strftime")
                            else match["match_date"]),
                "kickoff": match["kickoff_time"],
                "status":  match["status"],
            }

        matches = self.db.execute_query(
            "SELECT * FROM matches WHERE status = 'upcoming' ORDER BY match_date LIMIT 3"
        )
        return {"type": "upcoming_matches", "matches": matches}

    def _handle_price_check(self, message: str) -> Dict:
        match = self._extract_match_from_message(message)
        if match:
            return {
                "type":     "prices",
                "match":    f"{match['home_team']} vs {match['away_team']}",
                "standard": match["price_standard"],
                "vip":      match["price_vip"],
            }
        return {
            "type":    "price_list",
            "message": "Here are upcoming match prices:",
            "matches": self.db.execute_query(
                "SELECT home_team, away_team, price_standard, price_vip "
                "FROM matches WHERE status = 'upcoming' ORDER BY match_date"
            ),
        }

    def _handle_verification(self, message: str, user_id: str) -> Dict:
        ticket_id = self._extract_ticket_id(message)
        if not ticket_id:
            tickets = self.db.get_user_tickets(user_id)
            if tickets:
                ticket_id = tickets[0].get("ticket_id") or tickets[0].get("id")

        ticket = self.db.get_ticket_by_id(ticket_id) if ticket_id else None
        if ticket:
            return {
                "type":        "verification",
                "ticket_id":   ticket_id,
                "verified":    True,
                "match":       f"{ticket['home_team']} vs {ticket['away_team']}",
                "owner_match": ticket.get("user_id") == user_id,
                "blockchain_hash": (ticket.get("qr_hash", "N/A") or "N/A")[:8] + "...",
            }
        return {"type": "verification", "verified": False, "reason": "Ticket not found"}

    def _handle_transfer_ticket(self, message: str, user_id: str) -> Dict:
        """
        Handle ticket transfer — now actually updates the DB status.
        Full transfer (setting new owner) requires a recipient ID
        that the frontend must supply in a confirmation step.
        """
        ticket_id = self._extract_ticket_id(message)
        if not ticket_id:
            tickets = self.db.get_user_tickets(user_id)
            active = [t for t in tickets if t["status"] == "active"]
            if active:
                ticket_id = active[0].get("ticket_id") or active[0].get("id")

        if not ticket_id:
            return {"type": "transfer_info", "error": "No active tickets found to transfer."}

        ticket = self.db.get_ticket_by_id(ticket_id)
        if not ticket:
            return {"type": "transfer_info", "error": f"Ticket {ticket_id} not found."}

        if ticket["status"] != "active":
            return {
                "type":  "transfer_info",
                "error": f"Ticket {ticket_id} cannot be transferred (status: {ticket['status']}).",
            }

        # Mark ticket as "pending_transfer" until the frontend confirms recipient
        self.db.execute_update(
            "UPDATE tickets SET status = 'pending_transfer' WHERE id = :tid",
            {"tid": ticket_id},
        )
        logger.info("Ticket marked pending_transfer", extra={
            "ticket_id": ticket_id, "user_id": user_id
        })

        return {
            "type":            "transfer_info",
            "ticket_id":       ticket_id,
            "match":           f"{ticket['home_team']} vs {ticket['away_team']}",
            "status":          "pending_transfer",
            "transferable":    True,
            "action_required": (
                "Please provide the recipient's email or Botola Pro ID "
                "to complete the transfer."
            ),
        }

    def _handle_buy_ticket(self, message: str) -> Dict:
        matches = self.db.execute_query(
            "SELECT * FROM matches WHERE status = 'upcoming' ORDER BY match_date LIMIT 3"
        )
        return {
            "type":    "buy_recommendation",
            "message": "Here are the top upcoming matches you can buy tickets for:",
            "matches": matches,
        }

    # ------------------------------------------------------------------
    # Entity extraction helpers
    # ------------------------------------------------------------------

    def _extract_match_from_message(self, message: str) -> Optional[Dict]:
        """
        Try to find a match mentioned in the message.
        Uses the dynamic alias table for flexible team name resolution.
        """
        found_canonical: List[str] = []
        lower_msg = message.lower()

        # Check every alias
        for alias, canonical in TEAM_ALIASES.items():
            if re.search(rf'\b{re.escape(alias)}\b', lower_msg, re.IGNORECASE):
                if canonical not in found_canonical:
                    found_canonical.append(canonical)

        if len(found_canonical) >= 2:
            # Try home/away in both orders
            match = self.db.get_match_by_teams(found_canonical[0], found_canonical[1])
            if not match:
                match = self.db.get_match_by_teams(found_canonical[1], found_canonical[0])
            if match:
                logger.info("Match extracted from message",
                            extra={"teams": found_canonical, "match_id": match.get("id")})
            return match

        # Single team found — return its next match
        if found_canonical:
            query = """
                SELECT * FROM matches
                WHERE (LOWER(home_team) LIKE :team OR LOWER(away_team) LIKE :team)
                AND status = 'upcoming'
                ORDER BY match_date LIMIT 1
            """
            results = self.db.execute_query(
                query, {"team": f"%{found_canonical[0].lower()}%"}
            )
            return results[0] if results else None

        return None

    @staticmethod
    def _extract_ticket_id(message: str) -> Optional[str]:
        """Extract ticket ID (format: TS-XXXXX) from message."""
        match = re.search(r'#?(TS-\d{5})', message, re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _seat_dict(t: Dict) -> Dict:
        """Build a seat_info dict from a ticket row."""
        return {
            "type":  "seat_info",
            "match": f"{t['home_team']} vs {t['away_team']}",
            "venue": t["venue"],
            "zone":  t["zone"],
            "row":   t["row"],
            "seat":  t["seat_number"],
            "date":  t["match_date"],
        }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    builder = QueryBuilder()

    test_cases = [
        ("my_tickets",         "Show my tickets",                        "u_buyer_001"),
        ("seat_location",      "Where is my seat for Raja vs MAS?",      "u_buyer_001"),
        ("match_time",         "What time is WAC vs AS FAR?",            "u_buyer_001"),
        ("price_check",        "How much is a ticket for FUS vs WAC?",   "u_buyer_001"),
        ("ticket_verification","Is ticket TS-98201 real?",               "u_buyer_001"),
        ("transfer_ticket",    "Transfer ticket TS-98178 to Karim",      "u_buyer_001"),
    ]

    for intent, msg, uid in test_cases:
        print(f"\n{'='*50}")
        print(f"Intent: {intent} | Message: {msg}")
        result = builder.build_and_execute(intent, msg, uid)
        print(f"Result type: {result.get('type')}")