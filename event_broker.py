"""Streams conversation events to Rasa Aero's Observe panel.

Every deployed agent gets this baked in from the scaffold template — it's
not something AM authors. Configured via endpoints.yml's `event_broker:`
block (added once, when deploy is first configured — see
lib/agents/deploy.ts), pointing `url` at this agent's own event-ingestion
endpoint and `agent_slug` at its own slug.

Deliberately fire-and-forget: a failed POST (network hiccup, Rasa Aero
briefly down) must never break the conversation the broker is reporting on.
"""

import logging
from typing import Any, Dict, Text

import requests
import urllib3
from rasa.core.brokers.broker import EventBroker
from rasa.utils.endpoints import EndpointConfig

logger = logging.getLogger(__name__)

# Rasa Aero's own public URL is currently a self-signed cert (no domain
# pointed at the instance yet — see lib/agents/ec2.ts). Default cert
# verification would fail every single publish() call after its full
# timeout, turning "fire-and-forget telemetry" into several extra seconds
# of real delay per conversation turn (one publish per event, several
# events per turn) — confirmed live as exactly why replies looked stalled
# after the HTTPS migration. This is our own server, not a third party, so
# skipping verification here is the same narrowly-scoped tradeoff already
# made in lib/agents/deploy.ts's checkReachable — not a blanket disable.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HttpEventBroker(EventBroker):
    def __init__(self, url: Text, agent_slug: Text) -> None:
        self.url = url
        self.agent_slug = agent_slug

    @classmethod
    async def from_endpoint_config(
        cls, broker_config: EndpointConfig, event_loop=None
    ) -> "HttpEventBroker":
        return cls(
            url=broker_config.url,
            agent_slug=broker_config.kwargs.get("agent_slug", ""),
        )

    def publish(self, event: Dict[Text, Any]) -> None:
        try:
            requests.post(
                self.url,
                json={"agent_slug": self.agent_slug, "event": event},
                timeout=3,
                verify=False,
            )
        except Exception as e:
            logger.warning(f"HttpEventBroker: failed to publish event: {e}")

    def is_ready(self) -> bool:
        return True

    async def close(self) -> None:
        pass
