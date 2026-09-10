from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from tavily import TavilyClient
import os

class AgentState(TypedDict):
    tender_data: dict
    verifications: List[str]
    is_verified: bool
    iterations: int

tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

def build_query(tender: dict) -> str:
    parts = ["Ausschreibung", tender.get("title", "")]
    if tender.get("contractingAuthority"):
        parts.append(tender["contractingAuthority"])
    if tender.get("referenceNumber"):
        parts.append(f"Vergabenummer {tender['referenceNumber']}")
    parts.append("service.bund.de")
    return " ".join(p for p in parts if p)

def verify_tender_node(state: AgentState):
    tender = state['tender_data']
    query = build_query(tender)

    try:
        search_results = tavily.search(query=query, search_depth="basic")
        found = len(search_results.get('results', [])) > 0
    except Exception as e:
        print(f"Tavily search failed (non-fatal): {e}")
        found = False

    # Never hard-reject on a single search miss — flag instead, matching
    # the rest of the pipeline's flag-don't-discard design
    state['is_verified'] = True
    state['verifications'].append(
        "confirmed_via_search" if found else "unconfirmed_via_search"
    )
    state['iterations'] += 1
    return state

workflow = StateGraph(AgentState)
workflow.add_node("verifier", verify_tender_node)
workflow.set_entry_point("verifier")
workflow.add_edge("verifier", END)

app_graph = workflow.compile()