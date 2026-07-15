from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


class ActionMockRouteHumanSupport(Action):
    # MOCK — replace once a real MCP server for human-support-routing is registered.
    def name(self) -> Text:
        return "action_mock_route_human_support"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        """Create a deterministic mock ticket and return control to the handoff flow."""
        order_id = tracker.get_slot("order_id") or "not provided"
        item = tracker.get_slot("return_item") or "not provided"
        reason = tracker.get_slot("return_reason") or "not provided"
        eligibility = tracker.get_slot("return_eligibility") or "not checked"
        ticket_suffix = str(order_id)[-4:].upper() if order_id != "not provided" else "1001"
        ticket_id = f"SUP-{ticket_suffix}"
        summary = (
            f"Order: {order_id}; item: {item}; reason: {reason}; "
            f"eligibility: {eligibility}."
        )
        # Do not emit ConversationPaused: it prevents the following confirmation
        # response and END step from executing, leaving the flow incomplete.
        return [
            SlotSet("handoff_ticket_id", ticket_id),
            SlotSet("handoff_summary", summary),
        ]
