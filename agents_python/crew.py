import os
from crewai import Agent, LLM, Task, Crew, Process
from dotenv import load_dotenv

from crewai_tools import TavilySearchTool 

os.environ["OTEL_SDK_DISABLED"] = "true"

load_dotenv()



gateway_llm = LLM(
    model="openai/tender-crew-model",
    base_url="http://localhost:4000/v1",
    api_key="sk-1234"
)

search_tool = TavilySearchTool(max_results=2)

def create_tender_crew(tender_raw_data: dict, output_model):
    
    #The Fact Checker 
    fact_checker = Agent(
        role='Senior Tender Verifier',
        goal=f"Verify if the tender '{tender_raw_data.get('title')}' is actually being run by {tender_raw_data.get('contractingAuthority')}.",
        backstory="""You are a meticulous procurement researcher. Your job is to prevent hallucinations. 
        You use search engines to cross-reference tender reference numbers, contracting authorities, and submission status.""",
        tools=[search_tool],
        max_rpm=2,
        max_iter=3,
        max_tokens=2000,
        llm=gateway_llm, 
        verbose=True
    )

    #The Procurement Analyst 
    procurement_analyst = Agent(
        role='Procurement Analyst',
        goal="Refine the 'keywords' and 'summary' to be accurate and immediately useful to a bid team.",
        backstory="""You have reviewed thousands of EU tenders. You know the difference between 'Restricted' 
        and 'Negotiated' procedures. You ensure summaries are precise and never overstate scope. Your summary must be EXACTLY 1-2 sentences.""",
        llm=gateway_llm,
        max_tokens=1200,
        verbose=True
    )

    #Defining the Tasks
    verify_task = Task(
        description=f"Search for '{tender_raw_data.get('title')}' from {tender_raw_data.get('contractingAuthority')}. Confirm if it exists and if the reference number is correct.",
        expected_output="A brief report confirming the tender's validity and any corrected details.",
        agent=fact_checker
    )

    refine_task = Task(
        description=f"Based on the verification and this raw data: {tender_raw_data}, write a definitive Tender Dossier.",
        expected_output="A structured JSON object with tender details and a high-quality summary. Return ONLY a valid JSON object. Do not include any markdown formatting, backticks, or introductory text. Start your response with '{' and end with '}'.",
        agent=procurement_analyst,
        context=[verify_task],
        output_pydantic=output_model
    )

    #Assembling the Crew
    return Crew(
        agents=[fact_checker, procurement_analyst],
        tasks=[verify_task, refine_task],
        process=Process.sequential # Fact check first, then refine
    )
