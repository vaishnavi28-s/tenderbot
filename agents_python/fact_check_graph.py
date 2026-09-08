import re
from typing import TypedDict
from langgraph.graph import StateGraph, END


class FactCheckState(TypedDict):
    reference_number: str | None
    submission_deadline: str | None
    contracting_authority: str | None
    raw_content: str
    facts_checked: int
    facts_found: int
    verification_notes: list[str]
    facts_verified: bool


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def check_facts_node(state: FactCheckState) -> FactCheckState:
    raw_normalized = _normalize(state["raw_content"])
    notes = []
    checked = 0
    found = 0

    ref = state.get("reference_number")
    if ref:
        checked += 1
        if _normalize(ref) in raw_normalized:
            found += 1
            notes.append(f"Reference number '{ref}' found in source text.")
        else:
            notes.append(f"Reference number '{ref}' NOT found in source text.")

    deadline = state.get("submission_deadline")
    if deadline:
        checked += 1
        year_match = re.search(r"(20\d{2})", deadline)
        day_match = re.search(r"\b(\d{1,2})\b", deadline)
        year_ok = year_match and year_match.group(1) in state["raw_content"]
        day_ok = day_match and day_match.group(1) in state["raw_content"]
        if year_ok and day_ok:
            found += 1
            notes.append(f"Deadline '{deadline}' - year and day both found in source text.")
        else:
            notes.append(f"Deadline '{deadline}' - year and/or day NOT found in source text.")

    authority = state.get("contracting_authority")
    if authority:
        checked += 1
        if _normalize(authority) in raw_normalized:
            found += 1
            notes.append(f"Contracting authority '{authority}' found in source text.")
        else:
            notes.append(f"Contracting authority '{authority}' NOT found in source text.")

    return {
        **state,
        "facts_checked": checked,
        "facts_found": found,
        "verification_notes": notes,
    }


def route_after_check(state: FactCheckState) -> str:
    if state["facts_checked"] == 0:
        return "mark_verified"
    if state["facts_found"] >= state["facts_checked"] / 2:
        return "mark_verified"
    return "mark_flagged"


def mark_verified_node(state: FactCheckState) -> FactCheckState:
    return {**state, "facts_verified": True}


def mark_flagged_node(state: FactCheckState) -> FactCheckState:
    return {**state, "facts_verified": False}


def build_fact_check_graph():
    graph = StateGraph(FactCheckState)
    graph.add_node("check_facts", check_facts_node)
    graph.add_node("mark_verified", mark_verified_node)
    graph.add_node("mark_flagged", mark_flagged_node)

    graph.set_entry_point("check_facts")
    graph.add_conditional_edges(
        "check_facts", route_after_check,
        {"mark_verified": "mark_verified", "mark_flagged": "mark_flagged"}
    )
    graph.add_edge("mark_verified", END)
    graph.add_edge("mark_flagged", END)

    return graph.compile()


fact_check_app = build_fact_check_graph()


def run_fact_check(dossier: dict, raw_content: str) -> dict:
    """
    Returns {"facts_verified": bool, "verification_notes": [str, ...]}.
    """
    if not raw_content:
        return {"facts_verified": True, "verification_notes": ["No raw content available to check against."]}

    initial_state = {
        "reference_number": dossier.get("referenceNumber"),
        "submission_deadline": dossier.get("submissionDeadline"),
        "contracting_authority": dossier.get("contractingAuthority"),
        "raw_content": raw_content,
        "facts_checked": 0,
        "facts_found": 0,
        "verification_notes": [],
        "facts_verified": True,
    }
    result = fact_check_app.invoke(initial_state)
    return {
        "facts_verified": result["facts_verified"],
        "verification_notes": result["verification_notes"],
    }