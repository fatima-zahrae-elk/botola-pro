# chatbot-service/scripts/seed_database.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime, timedelta

from src.config import DATABASE_URL

Base = declarative_base()

# ============== MODELS ==============

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String)
    city = Column(String)
    trust_score = Column(Float, default=50.0)
    role = Column(String)  # buyer, seller, admin
    created_at = Column(DateTime, default=datetime.utcnow)


class Match(Base):
    __tablename__ = "matches"
    
    id = Column(String, primary_key=True)
    home_team = Column(String)
    away_team = Column(String)
    venue = Column(String)
    match_date = Column(DateTime)
    kickoff_time = Column(String)
    capacity = Column(Integer)
    tickets_sold = Column(Integer, default=0)
    status = Column(String)  # upcoming, live, completed
    price_standard = Column(Integer)
    price_vip = Column(Integer)


class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    match_id = Column(String, ForeignKey("matches.id"))
    zone = Column(String)
    seat_number = Column(String)
    row = Column(String)
    price = Column(Integer)
    status = Column(String)  # active, used, transferred, refunded
    qr_hash = Column(String)
    purchase_date = Column(DateTime)
    
    user = relationship("User", back_populates="tickets")
    match = relationship("Match", back_populates="tickets")


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True)
    ticket_id = Column(String, ForeignKey("tickets.id"))
    buyer_id = Column(String, ForeignKey("users.id"))
    seller_id = Column(String, ForeignKey("users.id"))
    amount = Column(Integer)
    fee = Column(Integer)
    status = Column(String)  # pending, completed, refunded
    created_at = Column(DateTime)


# Add relationships
User.tickets = relationship("Ticket", back_populates="user")
Match.tickets = relationship("Ticket", back_populates="match")


# ============== SEED DATA ==============

def seed_database():
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Users
    users = [
        User(id="u_buyer_001", email="yassine@example.com", first_name="Yassine", 
             last_name="El Amrani", phone="+212 661 234 567", city="Casablanca", 
             trust_score=98.0, role="buyer"),
        User(id="u_buyer_002", email="fatima@example.com", first_name="Fatima", 
             last_name="Zahra", phone="+212 662 345 678", city="Rabat", 
             trust_score=99.1, role="buyer"),
        User(id="u_seller_001", email="karim@example.com", first_name="Karim", 
             last_name="El Fassi", phone="+212 663 456 789", city="Casablanca", 
             trust_score=78.0, role="seller"),
        User(id="u_admin_001", email="admin@ss.com", first_name="System", 
             last_name="Admin", phone="+212 500 000 000", city="Casablanca", 
             trust_score=100.0, role="admin"),
    ]
    session.add_all(users)
    
    # Matches
    matches = [
        Match(id="m_001", home_team="WAC", away_team="AS FAR", 
              venue="Stade Mohammed V, Casablanca",
              match_date=datetime(2026, 4, 5, 20, 0),
              kickoff_time="20:00", capacity=60000, tickets_sold=42800,
              status="upcoming", price_standard=250, price_vip=2400),
        Match(id="m_002", home_team="Raja", away_team="MAS", 
              venue="Stade Mohammed V, Casablanca",
              match_date=datetime(2026, 4, 10, 18, 30),
              kickoff_time="18:30", capacity=60000, tickets_sold=35000,
              status="upcoming", price_standard=350, price_vip=1800),
        Match(id="m_003", home_team="FUS", away_team="WAC", 
              venue="Stade Moulay Abdallah, Rabat",
              match_date=datetime(2026, 4, 12, 16, 0),
              kickoff_time="16:00", capacity=45000, tickets_sold=18300,
              status="upcoming", price_standard=120, price_vip=800),
        Match(id="m_004", home_team="OCS", away_team="Raja", 
              venue="Stade Adrar, Agadir",
              match_date=datetime(2026, 4, 18, 20, 0),
              kickoff_time="20:00", capacity=35000, tickets_sold=12000,
              status="upcoming", price_standard=150, price_vip=600),
    ]
    session.add_all(matches)
    
    # Tickets (for Yassine)
    tickets = [
        Ticket(id="TS-98201", user_id="u_buyer_001", match_id="m_002",
               zone="Zone 04", seat_number="112", row="B",
               price=350, status="active", qr_hash="a1b2c3d4e5",
               purchase_date=datetime(2026, 3, 15)),
        Ticket(id="TS-98178", user_id="u_buyer_001", match_id="m_001",
               zone="Zone 02", seat_number="47", row="A",
               price=250, status="active", qr_hash="f6g7h8i9j0",
               purchase_date=datetime(2026, 3, 20)),
        Ticket(id="TS-97903", user_id="u_buyer_001", match_id="m_003",
               zone="Tribune", seat_number="B-14", row="B",
               price=120, status="used", qr_hash="k1l2m3n4o5",
               purchase_date=datetime(2026, 2, 10)),
    ]
    session.add_all(tickets)
    
    # Transactions
    transactions = [
        Transaction(id="tx_001", ticket_id="TS-98201", buyer_id="u_buyer_001",
                   seller_id="u_seller_001", amount=350, fee=7,
                   status="completed", created_at=datetime(2026, 3, 15)),
    ]
    session.add_all(transactions)
    
    session.commit()
    session.close()
    
    print("Database seeded successfully!")
    print(f"  Users: {len(users)}")
    print(f"  Matches: {len(matches)}")
    print(f"  Tickets: {len(tickets)}")
    print(f"  Transactions: {len(transactions)}")


if __name__ == "__main__":
    seed_database()