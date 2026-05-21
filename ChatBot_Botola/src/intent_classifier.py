# chatbot-service/src/intent_classifier.py
"""
Embedding-based intent classifier with language detection.

Replaces the fragile regex approach with semantic similarity:
1. Each intent has a set of example queries in EN/FR/AR/Darija.
2. At classification time, the user's query is embedded and compared
   against ALL example embeddings via cosine similarity.
3. The intent whose examples have the highest average similarity wins.

This handles paraphrases, mixed languages, and ambiguous phrasing
far better than keyword counting.
"""
import numpy as np
from typing import Dict, List, Tuple

from langdetect import detect, LangDetectException
from sentence_transformers import SentenceTransformer

from .config import STATIC_INTENTS, DYNAMIC_INTENTS, CONFIDENCE_THRESHOLD, EMBEDDING_MODEL
from .logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Intent example bank
# ---------------------------------------------------------------------------
# Each intent has representative queries in multiple languages.
# Add more examples to improve accuracy for under-represented patterns.
# ---------------------------------------------------------------------------
INTENT_EXAMPLES: Dict[str, List[str]] = {
    # ── STATIC intents ──────────────────────────────────────────────────────
    "smalltalk": [
        "hi", "hello", "hey", "bonjour", "salam", "ahlan", "marhba",
        "merci", "choukrane", "shukran", "thanks", "thank you", "ok", "bye",
        "bslama", "la bas", "oui", "yes", "no", "okay",
    ],
    "bag_policy": [
        "Can I bring a bag to the stadium?",
        "Are backpacks allowed?",
        "Is my bag permitted?",
        "Est-ce que je peux amener un sac?",
        "هل يمكنني إحضار حقيبة؟",
        "wach imken liya njibi sac?",
        "What bags are allowed?",
        "Can I carry a purse?",
        "Large backpack allowed?",
        "sac à dos autorisé?",
    ],
    "gate_time": [
        "When do the gates open?",
        "What time does the stadium open?",
        "When can I enter?",
        "À quelle heure ouvrent les portes?",
        "متى تفتح بوابات الملعب؟",
        "imta tftah bwabat?",
        "What time should I arrive?",
        "How early can I go in?",
        "Quelle heure d'ouverture?",
    ],
    "prohibited_items": [
        "What items are not allowed?",
        "What is prohibited in the stadium?",
        "Can I bring a camera?",
        "Are flares banned?",
        "Qu'est-ce qui est interdit?",
        "ما هي الأشياء الممنوعة؟",
        "wach imken njibi camera?",
        "Weapons allowed?",
        "Is alcohol permitted?",
    ],
    "food_policy": [
        "Can I bring food?",
        "Is outside food allowed?",
        "Can I bring water?",
        "What food can I bring?",
        "Est-ce que je peux amener à manger?",
        "هل يمكنني إحضار طعام؟",
        "Can I bring a snack?",
        "Are drinks allowed?",
        "Can I eat inside the stadium?",
    ],
    "parking": [
        "Is there parking?",
        "Where can I park?",
        "Parking near the stadium?",
        "Y a-t-il un parking?",
        "هل يوجد موقف سيارات؟",
        "fin nrked tomobile?",
        "How do I get to the stadium by car?",
        "Public transport options?",
        "Tram to the stadium?",
    ],
    "accessibility": [
        "Wheelchair access?",
        "Is the stadium accessible for disabled?",
        "Handicap entrance?",
        "Accès pour les personnes handicapées?",
        "هل يوجد مدخل لذوي الاحتياجات الخاصة?",
        "Elevator at the stadium?",
        "Companion seating?",
    ],
    "faq": [
        "How does the dynamic QR code work?",
        "What is the refund policy?",
        "How does ticket transfer work?",
        "Comment fonctionne le QR code?",
        "كيف يعمل نظام التذاكر؟",
        "Can I get a refund?",
        "What if it rains?",
        "Can I bring my child?",
        "Children free entry?",
    ],
    # ── DYNAMIC intents ─────────────────────────────────────────────────────
    "my_tickets": [
        "Show my tickets",
        "What tickets do I have?",
        "List my bookings",
        "Afficher mes billets",
        "أظهر تذاكري",
        "wach 3andi tickets?",
        "My bookings",
        "My reservations",
        "Voir mes tickets",
    ],
    "seat_location": [
        "Where is my seat?",
        "What is my seat number?",
        "Which zone am I in?",
        "Where do I sit?",
        "Où est ma place?",
        "أين مقعدي؟",
        "win kayna blasti?",
        "My seat for the match",
        "Zone and row for my ticket",
        "Where is my seat for WAC vs FAR?",
        "Where is my seat for Raja vs MAS?",
    ],
    "match_time": [
        "What time does the match start?",
        "When is the match?",
        "What is the kickoff time?",
        "À quelle heure commence le match?",
        "متى يبدأ المباراة؟",
        "imta kaybda match?",
        "What time is WAC vs FAR?",
        "Kickoff time for Raja?",
        "When does the game start?",
    ],
    "price_check": [
        "How much is a ticket?",
        "What is the price?",
        "How much does a VIP ticket cost?",
        "Quel est le prix?",
        "بكم التذكرة؟",
        "shhal ticket?",
        "Cost of standard ticket?",
        "Ticket prices?",
        "How much for tonight's match?",
    ],
    "buy_ticket": [
        "I want to buy a ticket",
        "How can I get a ticket?",
        "Buy tickets online",
        "Which match should I attend?",
        "Recommend a match",
        "Je veux acheter un billet",
        "أريد شراء تذكرة",
        "bghit nshri ticket",
        "Available tickets?",
        "Best match to buy?",
    ],
    "ticket_status": [
        "What is the status of my ticket?",
        "Is my ticket valid?",
        "Check ticket status",
        "Quel est le statut de mon billet?",
        "ما حالة تذكرتي؟",
        "Is my ticket still active?",
        "Check my booking status",
    ],
    "ticket_verification": [
        "Is this ticket real?",
        "Verify my ticket",
        "Is my ticket authentic?",
        "Vérifier mon billet",
        "هل تذكرتي حقيقية؟",
        "Is ticket TS-98201 valid?",
        "Authenticate my ticket",
        "Blockchain verification",
    ],
    "transfer_ticket": [
        "Transfer my ticket to Karim",
        "Send my ticket to someone",
        "Give my ticket to a friend",
        "Transférer mon billet",
        "تحويل تذكرتي",
        "bghit n3ti ticket l sahbi",
        "How to transfer?",
        "Can I give my ticket away?",
    ],
}


class IntentClassifier:
    """
    Embedding-based intent classifier with language detection.

    On first call to `classify()`, example queries are embedded and cached.
    Subsequent calls only embed the (single) user query — fast at runtime.
    """

    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self._intent_embeddings: Dict[str, np.ndarray] = {}
        self._build_index()

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_index(self):
        """Pre-embed all intent examples and cache mean vectors."""
        logger.info("Building intent embedding index...")
        for intent, examples in INTENT_EXAMPLES.items():
            vecs = self.model.encode(examples, normalize_embeddings=True)
            # Store both the mean (for fast lookup) and all vecs (for max-pool)
            self._intent_embeddings[intent] = vecs
        logger.info("Intent index ready", extra={"num_intents": len(self._intent_embeddings)})

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, text: str) -> Dict:
        """
        Classify user query into intent, confidence, and route.

        Returns:
            {
                "intent":     str,
                "confidence": float,          # 0.0 – 1.0
                "route":      "static" | "dynamic" | "unknown",
                "language":   str,            # ISO 639-1 code
                "all_scores": {intent: score, ...}
            }
        """
        # ── Language detection ─────────────────────────────────────────
        try:
            language = detect(text)
        except LangDetectException:
            language = "unknown"

        # ── Embed query ────────────────────────────────────────────────
        query_vec = self.model.encode([text], normalize_embeddings=True)[0]  # shape (D,)

        # ── Score each intent ──────────────────────────────────────────
        scores: Dict[str, float] = {}
        for intent, example_vecs in self._intent_embeddings.items():
            # Use MAX similarity across examples (soft nearest-neighbor)
            sims = example_vecs @ query_vec          # shape (N_examples,)
            scores[intent] = float(sims.max())

        # ── Pick best intent ───────────────────────────────────────────
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # ── Determine route ────────────────────────────────────────────
        if best_score < CONFIDENCE_THRESHOLD:
            route = "unknown"
        elif best_intent in STATIC_INTENTS:
            route = "static"
        elif best_intent in DYNAMIC_INTENTS:
            route = "dynamic"
        else:
            route = "unknown"

        # Only expose scores above a noise floor in the debug payload
        top_scores = {k: round(v, 3) for k, v in scores.items() if v > 0.3}

        logger.info("Intent classified", extra={
            "intent": best_intent,
            "confidence": round(best_score, 3),
            "route": route,
            "language": language,
        })

        return {
            "intent": best_intent,
            "confidence": round(best_score, 3),
            "route": route,
            "language": language,
            "all_scores": top_scores,
        }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    classifier = IntentClassifier()

    test_queries = [
        "Can I bring a backpack?",
        "Where is my seat for WAC vs FAR?",
        "Is my ticket verified?",
        "What time does the match start?",
        "How much is a VIP ticket?",
        "Transfer my ticket to Karim",
        "متى تفتح بوابات الملعب؟",
        "أين مقعدي؟",
        "bghit nshri ticket",
        "wach imken njibi sac?",
        "Show me my tickets",
        "What are the betting odds?",  # should → blocked by guardrails upstream
    ]

    for q in test_queries:
        result = classifier.classify(q)
        print(f"\nQuery: {q}")
        print(f"  Intent: {result['intent']} ({result['confidence']:.3f})")
        print(f"  Route: {result['route']} | Lang: {result['language']}")