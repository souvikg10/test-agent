import re
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


class ValidateFallbackLookupDetails(Action):
    def name(self) -> Text:
        return "validate_fallback_lookup_details"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        details = str(tracker.get_slot("fallback_lookup_details") or "").strip()
        normalized = details.lower()
        sensitive_terms = ("password", "passcode", "verification code", "one-time code", "otp", "cvv", "security code")
        # These patterns deliberately reject both terse and natural-language refusals.
        refusal_pattern = re.compile(
            r"^(?:no|nope|none|nothing|n/?a|skip|rather not|not providing|"
            r"i (?:do not|don't|won't|will not|refuse to) (?:have|provide|give|share).*)$"
        )
        card_like_number = bool(re.search(r"(?:\d[ -]?){13,19}", details))
        if any(term in normalized for term in sensitive_terms) or card_like_number:
            dispatcher.utter_message(response="utter_sensitive_lookup_details")
            return [SlotSet("fallback_lookup_details", None)]
        # Empty and refused values must stay null so lookup_order can never receive them.
        if not details or refusal_pattern.fullmatch(normalized):
            return [SlotSet("fallback_lookup_details", None)]
        return [SlotSet("fallback_lookup_details", details)]


class ActionMockLookupOrder(Action):
    # MOCK — replace once a real MCP server for order-management-mcp is registered.
    def name(self) -> Text:
        return "action_mock_lookup_order"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        order_id = str(tracker.get_slot("order_id") or "").strip().lower()
        fallback = str(tracker.get_slot("fallback_lookup_details") or "").strip().lower()
        failures = float(tracker.get_slot("order_lookup_failure_count") or 0)
        key = order_id or fallback
        if not key or "nomatch" in key or key.endswith("0000"):
            return [SlotSet("order_lookup_status", "no_match"), SlotSet("order_lookup_failure_count", failures + 1)]
        if "multiple" in key or key.endswith("1111"):
            return [SlotSet("order_lookup_status", "multiple_matches"), SlotSet("order_lookup_failure_count", failures + 1)]
        if order_id == "r1002":
            summary = "order R1002 with Winter Boots"
        else:
            summary = f"order {order_id.upper()} with a Blue Hoodie and Everyday Sneakers" if order_id else "an order matching the details you provided with a Blue Hoodie and Everyday Sneakers"
        return [SlotSet("order_lookup_status", "matched"), SlotSet("matched_order_summary", summary), SlotSet("order_lookup_failure_count", 0)]


class ActionMockCheckReturnEligibility(Action):
    # MOCK — replace once a real MCP server for order-management-mcp is registered.
    def name(self) -> Text:
        return "action_mock_check_return_eligibility"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        order_id = str(tracker.get_slot("order_id") or "").lower()
        item = str(tracker.get_slot("return_item") or "").lower()
        key = f"{order_id} {item}"
        # R1002 is the deterministic past-window mock fixture and contains Winter Boots.
        if (order_id == "r1002" and "winter boots" in item) or order_id.endswith("9999") or "past window" in key:
            result = "past_window"
        elif order_id.endswith("8888") or "already refunded" in key:
            result = "already_refunded"
        elif order_id.endswith("7777") or "open return" in key:
            result = "open_return"
        elif "final sale" in key:
            result = "restricted"
        else:
            result = "eligible"
        return [SlotSet("return_eligibility", result)]


class ActionMockCreateReturn(Action):
    # MOCK — replace once a real MCP server for order-management-mcp is registered.
    def name(self) -> Text:
        return "action_mock_create_return"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        order_id = str(tracker.get_slot("order_id") or "fallback").upper()
        item = str(tracker.get_slot("return_item") or "item").lower()
        if "creation failure" in item or order_id.endswith("6666"):
            return [SlotSet("return_creation_status", "failed")]
        authorization = f"RA-{order_id[-4:] if len(order_id) >= 4 else '1001'}"
        return [SlotSet("return_creation_status", "created"), SlotSet("return_authorization", authorization)]
