"""Toy agent: a scripted "trip planner" that records a full flight-recorder run.

Runs entirely offline — model responses are canned and tools are fakes (one
of them fails on purpose so you can see error highlighting in the UI).

Usage:
    1. start the backend:  cd backend && python -m app
    2. run this:           python examples/toy_agent/toy_agent.py
    3. inspect:            afr runs list   /   open http://127.0.0.1:8700
"""

from __future__ import annotations

import random

import afr


# --- fake model -------------------------------------------------------------

CANNED = {
    "plan": "1) find flights to Tokyo 2) find a hotel 3) build day-by-day itinerary",
    "itinerary": "Day 1: Asakusa & Skytree. Day 2: Ghibli Museum. Day 3: day trip to Kamakura.",
}


@afr.record_model_call(model="toy-llm-1", provider="canned")
def ask_model(prompt: str) -> str:
    for key, answer in CANNED.items():
        if key in prompt:
            return answer
    return "I can only plan trips in this demo."


# --- fake tools ---------------------------------------------------------------

_hotel_attempts = {"count": 0}


@afr.record_tool_call
def search_flights(destination: str, budget_usd: int) -> dict:
    return {
        "destination": destination,
        "carrier": "Orchid Air",
        "price_usd": min(budget_usd, 512),
        "flight": "OA-117",
    }


@afr.record_tool_call
def search_hotels(city: str, nights: int) -> dict:
    _hotel_attempts["count"] += 1
    if _hotel_attempts["count"] == 1:
        raise TimeoutError("hotel inventory service timed out (toy failure for the demo)")
    return {"city": city, "hotel": "Hotel Magenta", "nights": nights, "price_usd": 140 * nights}


# --- the agent ----------------------------------------------------------------


def main() -> None:
    random.seed(7)

    with afr.start_run("toy-trip-planner", metadata={"example": True, "destination": "Tokyo"}) as run:
        print(f"recording run {run.run_id}")

        afr.log("agent starting", goal="plan a 3-night Tokyo trip under $2000")

        plan = ask_model("plan a trip to Tokyo")
        afr.log_state({"goal": "tokyo-trip", "plan": plan, "booked": {}})

        flights = search_flights("Tokyo", budget_usd=900)
        afr.log_state({"booked": {"flight": flights}}, mode="merge")
        ckpt1 = afr.checkpoint("after-flights")
        print(f"checkpoint after-flights: {ckpt1['id']}")

        try:
            hotel = search_hotels("Tokyo", nights=3)
        except TimeoutError:
            afr.log("retrying hotel search after timeout", level="warning")
            hotel = search_hotels("Tokyo", nights=3)
        afr.log_state({"booked": {"hotel": hotel}}, mode="merge")
        ckpt2 = afr.checkpoint("after-hotel")
        print(f"checkpoint after-hotel:   {ckpt2['id']}")

        itinerary = ask_model("write the itinerary")
        afr.log_state(
            {"itinerary": itinerary, "total_usd": flights["price_usd"] + hotel["price_usd"]},
            mode="merge",
        )
        afr.checkpoint("final")
        afr.log("agent finished", level="info")

        print()
        print("done — inspect with:")
        print(f"  afr runs show {run.run_id[:8]}")
        print(f"  afr events {run.run_id[:8]}")
        print(f"  afr replay {run.run_id[:8]} --from {ckpt1['id'][:8]} \\")
        print("      --mode mock_tools --handler examples.toy_agent.replay_handler:resume")


if __name__ == "__main__":
    main()
