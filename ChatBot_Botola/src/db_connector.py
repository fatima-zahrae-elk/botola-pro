# chatbot-service/src/db_connector.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional, Any
import json
import logging

from .config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DBConnector:
    """
    Interface to the Botola Pro database.
    Provides both ORM and raw SQL capabilities.
    """
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
    
    def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute a raw SQL query and return results as dicts."""
        session = self.Session()
        try:
            result = session.execute(text(query), params or {})
            rows = [dict(row._mapping) for row in result]
            return rows
        finally:
            session.close()

    def execute_update(self, query: str, params: Dict = None) -> int:
        """Execute a raw SQL update/insert/delete and return row count."""
        session = self.Session()
        try:
            result = session.execute(text(query), params or {})
            session.commit()
            logger.info(f"Executed update: {query[:50]}... | Rows affected: {result.rowcount}")
            return result.rowcount
        except Exception as e:
            session.rollback()
            logger.error(f"Error executing update: {e}")
            raise
        finally:
            session.close()
    
    def get_user_tickets(self, user_id: str) -> List[Dict]:
        """Get all tickets for a user with match details."""
        query = """
            SELECT t.id as ticket_id, t.zone, t.seat_number, t.row,
                   t.price, t.status, t.qr_hash,
                   m.home_team, m.away_team, m.venue,
                   m.match_date, m.kickoff_time
            FROM tickets t
            JOIN matches m ON t.match_id = m.id
            WHERE t.user_id = :user_id
            ORDER BY m.match_date
        """
        return self.execute_query(query, {"user_id": user_id})
    
    def get_ticket_by_id(self, ticket_id: str) -> Optional[Dict]:
        """Get specific ticket details."""
        query = """
            SELECT t.*, m.home_team, m.away_team, m.venue, m.match_date
            FROM tickets t
            JOIN matches m ON t.match_id = m.id
            WHERE t.id = :ticket_id
        """
        results = self.execute_query(query, {"ticket_id": ticket_id})
        return results[0] if results else None
    
    def get_match_details(self, match_id: str) -> Optional[Dict]:
        """Get match details."""
        query = "SELECT * FROM matches WHERE id = :match_id"
        results = self.execute_query(query, {"match_id": match_id})
        return results[0] if results else None
    
    def get_match_by_teams(self, home: str, away: str) -> Optional[Dict]:
        """Find match by team names."""
        query = """
            SELECT * FROM matches 
            WHERE LOWER(home_team) LIKE :home 
            AND LOWER(away_team) LIKE :away
            AND status = 'upcoming'
            ORDER BY match_date LIMIT 1
        """
        results = self.execute_query(query, {
            "home": f"%{home.lower()}%",
            "away": f"%{away.lower()}%"
        })
        return results[0] if results else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Find user by email."""
        query = "SELECT * FROM users WHERE email = :email"
        results = self.execute_query(query, {"email": email})
        return results[0] if results else None


# Quick test
if __name__ == "__main__":
    db = DBConnector()
    
    print("=== Yassine's Tickets ===")
    tickets = db.get_user_tickets("u_buyer_001")
    for t in tickets:
        print(f"{t['ticket_id']}: {t['home_team']} vs {t['away_team']} | "
              f"Zone {t['zone']} Seat {t['seat_number']} | {t['status']}")
    
    print("\n=== Match WAC vs FAR ===")
    match = db.get_match_by_teams("WAC", "FAR")
    if match:
        print(f"{match['venue']} | {match['match_date']} | {match['price_standard']} MAD")