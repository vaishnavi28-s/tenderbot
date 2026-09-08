from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from tavily import TavilyClient
import os

#Defining the State 
class AgentState(TypedDict):
    tender_data: dict
    verifications: List[str]
    is_verified: bool
    iterations: int

tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

#Node: Verification Logic
def verify_tender_node(state: AgentState):
    tender = state['tender_data']
    query = f"Ausschreibung {tender['title']} {tender['contractingAuthority']} Vergabenummer {tender.get('referenceNumber', '')} service.bund.de"
    
    # Automatic search
    search_results = tavily.search(query=query, search_depth="basic")
    
    # If search finds matches, mark as verified
    state['is_verified'] = len(search_results.get('results', [])) > 0
    state['iterations'] += 1
    return state

#Create the Graph
workflow = StateGraph(AgentState)
workflow.add_node("verifier", verify_tender_node)
workflow.set_entry_point("verifier")

#Conditional Edge: If not verified, we could route back to Mastra
workflow.add_edge("verifier", END)

app_graph = workflow.compile()
