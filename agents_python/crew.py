import os
from crewai import Agent, LLM, Task, Crew, Process
from dotenv import load_dotenv

from crewai_tools import TavilySearchTool


load_dotenv()
from langsmith.integrations.otel import OtelSpanProcessor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

current_provider = trace.get_tracer_provider()
if isinstance(current_provider, TracerProvider):
    tracer_provider = current_provider
else:
    tracer_provider = TracerProvider()
    trace.set_tracer_provider(tracer_provider)

tracer_provider.add_span_processor(OtelSpanProcessor())
CrewAIInstrumentor().instrument(tracer_provider=tracer_provider)
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
gateway_llm = LLM(
    model="openai/tender-verify-model",
    base_url="http://localhost:4000/v1",
    api_key="sk-1234",
    temperature=0
)

search_tool = TavilySearchTool(max_results=2)

def create_verification_crew(dossier: dict):
    fact_checker = Agent(
        role='Senior Tender Verifier',
        goal=f"Check whether '{dossier.get('title')}' is genuinely run by {dossier.get('contractingAuthority')}, using only web search results as evidence.",
        backstory="""You are a meticulous procurement researcher. You NEVER invent or guess a fact —
        you only report what a search result explicitly states. If search results don't clearly confirm
        or contradict a claim, you report 'unconfirmed', never a guess. You have exactly ONE tool
        available: web search. Do not attempt to use any other tool or function.""",
        tools=[search_tool],
        max_rpm=2,
        max_iter=2,
        max_tokens=1000,
        llm=gateway_llm,
        verbose=True
    )

    verify_task = Task(
        description=(
            f"Search for '{dossier.get('title')}' from '{dossier.get('contractingAuthority')}'. "
            f"For the fields contractingAuthority and referenceNumber (current values: "
            f"{dossier.get('contractingAuthority')}, {dossier.get('referenceNumber')}), "
            f"determine if search results CONFIRM, CONTRADICT, or leave UNCONFIRMED each value. "
            f"If CONTRADICT, quote the exact evidence snippet from the search result."
        ),
        expected_output=(
            "A JSON list of objects, one per checked field, each with: "
            "field, claimed_value, verdict (confirmed/contradicted/unconfirmed), evidence_snippet (or null)."
        ),
        agent=fact_checker
    )

    return Crew(
        agents=[fact_checker],
        tasks=[verify_task],
        process=Process.sequential
    )