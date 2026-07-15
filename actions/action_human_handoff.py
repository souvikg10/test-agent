from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import ConversationPaused, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


class ActionMockRouteHumanSupport(Action):
    # MOCK — replace once a real MCP server for human-support-routing is registered.
    def name(self) -> Text:
        return "action_mock_route_human_support"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        order_id = tracker.get_slot("order_id") or "not provided"
        item = tracker.get_slot("return_item") or "not provided"
        reason = tracker.get_slot("return_reason") or "not provided"
        eligibility = tracker.get_slot("return_eligibility") or "not checked"
        ticket_id = f"SUP-{str(order_id)[-4:].upper() if order_id != 'not provided' else '1001'}"
        summary = f"Order: {order_id}; item: {item}; reason: {reason}; eligibility: {eligibility}."
        # Pause automation after the ticket is created so later messages are handled by live support,
        # rather than repeatedly restarting a return flow.
        return [
            SlotSet("handoff_ticket_id", ticket_id),
            SlotSet("handoff_summary", summary),
            ConversationPaused(),
        ]
