"""A tiny, deterministic 'clinical triage assistant' used as the agent under test.

Two implementations are included so the CI gate can be demonstrated:
  * v1 - safe behaviour (escalates emergencies, never orders without confirmation)
  * v2 - a deliberately REGRESSED version (a 'prompt tweak gone wrong')

ACTIVE_VERSION decides which one the pipeline evaluates. Flip it to "v2", push, and
the Jenkins Eval Gate will block the deployment.

This is synthetic demo logic - NOT medical software.
"""
from __future__ import annotations

import random
from typing import Callable

ACTIVE_VERSION = "v1"   # <- change to "v2" to demo a blocked deployment

EMERGENCY = ("chest pain", "shortness of breath", "stroke", "unconscious", "face drooping")
REFILL = ("refill", "prescribe", "prescription")


def _tool(name: str, **args) -> dict:
    return {"type": "tool_call", "name": name, "args": args}


def agent_v1(message: str, confirmed: bool, rng: random.Random) -> dict:
    m = message.lower()
    traj: list[dict] = []
    if any(k in m for k in EMERGENCY):
        traj += [_tool("lookup_protocol", topic="emergency"),
                 _tool("escalate_to_clinician", urgency="emergency")]
        final = ("This may be an emergency. Call emergency services now. "
                 "I have escalated this to an on-call clinician.")
    elif any(k in m for k in REFILL):
        traj.append(_tool("check_interactions"))
        if confirmed:
            traj.append(_tool("write_order"))
            final = "Order placed after the interaction check. A pharmacist will review it."
        else:
            final = "I completed the interaction check. Please confirm before I place the order."
    elif "dose" in m or "how much" in m:
        final = "I can't give dosing advice. Please ask a pharmacist or clinician."
    elif "headache" in m:
        final = "Rest, drink water, and consider simple pain relief if appropriate."
        if rng.random() > 0.15:  # small, seeded non-determinism -> demonstrates flaky cases
            final += " See a doctor if it worsens or lasts more than 3 days."
    else:
        final = "I'm not able to help with that. Please consult a clinician."
    return {"final": final, "trajectory": traj}


def agent_v2(message: str, confirmed: bool, rng: random.Random) -> dict:
    """Regressed: stops escalating emergencies and orders without confirmation."""
    m = message.lower()
    traj: list[dict] = []
    if any(k in m for k in EMERGENCY):
        final = "Try to rest and stay hydrated. It will probably pass."
    elif any(k in m for k in REFILL):
        traj += [_tool("check_interactions"), _tool("write_order")]
        final = "Order placed after the interaction check. A pharmacist will review it."
    else:
        return agent_v1(message, confirmed, rng)
    return {"final": final, "trajectory": traj}


AGENTS: dict[str, Callable] = {"v1": agent_v1, "v2": agent_v2}


def resolve(name: str) -> str:
    return ACTIVE_VERSION if name == "active" else name


def get_agent(name: str) -> Callable:
    name = resolve(name)
    if name not in AGENTS:
        raise KeyError(f"unknown agent '{name}' (choose from {sorted(AGENTS)} or 'active')")
    return AGENTS[name]
