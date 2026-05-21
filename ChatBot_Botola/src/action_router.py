# chatbot-service/src/action_router.py
from typing import Dict, Optional
from enum import Enum


class ActionType(Enum):
    CHAT_REPLY = "chat_reply"
    MAP_LINK = "map"
    PUSH_NOTIFICATION = "push"
    ADMIN_ALERT = "admin_alert"
    HUMAN_HANDOFF = "human"


class ActionRouter:
    """
    Routes chatbot outputs to appropriate action channels.
    """
    
    def route(self, intent: str, data: Dict, confidence: float) -> Dict:
        """
        Determine action type and payload based on intent and data.
        """
        from .config import CONFIDENCE_THRESHOLD
        # High-confidence dynamic queries with location data → Map
        if intent in ["seat_location"] and confidence > 0.7:
            return {
                "type": ActionType.MAP_LINK.value,
                "payload": {
                    "venue": data.get("venue", ""),
                    "zone": data.get("zone", ""),
                    "seat": data.get("seat", ""),
                    "map_url": self._generate_map_url(data)
                },
                "message": data.get("formatted_response", "")
            }
        
        # Fraud or security issues → Admin alert
        if intent in ["fraud_report", "security_issue"] or data.get("fraud_detected"):
            return {
                "type": ActionType.ADMIN_ALERT.value,
                "payload": {
                    "alert_level": "high",
                    "category": "user_reported",
                    "details": data
                },
                "message": "🚨 Your report has been forwarded to our security team. Thank you for keeping Botola Pro safe."
            }
        
        # Low confidence → Human handoff
        if confidence < CONFIDENCE_THRESHOLD:
            return {
                "type": ActionType.HUMAN_HANDOFF.value,
                "payload": {
                    "queue": "general_support",
                    "priority": "normal",
                    "context": data
                },
                "message": "I'm not sure I understand. Let me connect you with a human agent who can help."
            }
        
        # Ticket reminders → Push notification
        if intent in ["match_reminder", "gate_opening"]:
            return {
                "type": ActionType.PUSH_NOTIFICATION.value,
                "payload": {
                    "title": "Botola Pro Match Day",
                    "body": data.get("message", ""),
                    "scheduled_time": data.get("send_at")
                },
                "message": "✅ Reminder set! You'll receive a notification."
            }
        
        # Default: chat reply
        return {
            "type": ActionType.CHAT_REPLY.value,
            "payload": {},
            "message": data.get("formatted_response", data.get("message", ""))
        }
    
    def _generate_map_url(self, data: Dict) -> str:
        """Generate stadium map URL."""
        venue = data.get("venue", "").lower().replace(" ", "-").replace(",", "")
        zone = data.get("zone", "").replace(" ", "-").lower()
        return f"/maps/{venue}?zone={zone}&highlight={data.get('seat', '')}"
    
    def format_for_frontend(self, action: Dict) -> Dict:
        """Format action for frontend consumption."""
        return {
            "type": action["type"],
            "message": action["message"],
            "data": action.get("payload", {}),
            "actions": self._get_frontend_actions(action["type"], action.get("payload", {}))
        }
    
    def _get_frontend_actions(self, action_type: str, payload: Dict) -> list:
        """Generate actionable buttons for frontend."""
        actions = []
        
        if action_type == ActionType.MAP_LINK.value:
            actions.append({
                "label": "View Stadium Map",
                "action": "open_map",
                "url": payload.get("map_url")
            })
            actions.append({
                "label": "Get Directions",
                "action": "open_directions",
                "url": f"/directions?to={payload.get('venue', '')}"
            })
        
        elif action_type == ActionType.HUMAN_HANDOFF.value:
            actions.append({
                "label": "Chat with Agent",
                "action": "open_chat",
                "url": "/support/live"
            })
        
        elif action_type == ActionType.PUSH_NOTIFICATION.value:
            actions.append({
                "label": "Manage Notifications",
                "action": "open_settings",
                "url": "/settings/notifications"
            })
        
        return actions


# Quick test
if __name__ == "__main__":
    router = ActionRouter()
    
    test_cases = [
        ("seat_location", {"venue": "Stade Mohammed V", "zone": "04", "seat": "112", "formatted_response": "Your seat is..."}, 0.9),
        ("bag_policy", {"formatted_response": "Bags must be..."}, 0.8),
        ("unknown", {"formatted_response": "..."}, 0.3),
    ]
    
    for intent, data, conf in test_cases:
        result = router.route(intent, data, conf)
        frontend = router.format_for_frontend(result)
        print(f"\nIntent: {intent}")
        print(f"Action: {frontend['type']}")
        print(f"Buttons: {[a['label'] for a in frontend['actions']]}")