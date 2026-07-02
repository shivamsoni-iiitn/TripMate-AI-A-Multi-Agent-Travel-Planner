import os 
import certifi
from dotenv import load_dotenv
import warnings

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic"
)

os.environ['SSL_CERT_FILE'] = certifi.where()   
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

load_dotenv()
from typing import TypedDict, Annotated
import operator
import uuid

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_openai.chat_models import ChatOpenAI
from tools.tavily_toll import tavily_search 
from tools.flight_tool import search_flights

def get_database_url():
    database_url=os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is missing. Please add your database url in .env file")
    
    if "sslmode=" not in database_url:
        seperator = "&" if "?" in database_url else "?"
        database_url += f"{seperator}sslmode=require"
    return database_url

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing. Please add your OpenAI API key in .env file")

#LLM
llm=ChatOpenAI(
    model="gpt-5-nano",
    openai_api_key=OPENAI_API_KEY,
    temperature=0.7,
)

#State
class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int

#Flight Agent
def flight_agent(state: TravelState) -> TravelState:
    query=state["user_query"]
    flight_data=search_flights(query)
    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

from langchain_core.prompts import ChatPromptTemplate

hotel_search_prompt = ChatPromptTemplate.from_messages([
(
"system",
"""
You are a hotel search planner.

Convert the user's travel request into ONE search query that can be sent to a hotel search engine.

Guidelines:

- Focus ONLY on the destination.
- Ignore departure city.
- If multiple cities exist, choose the first major tourist city.
- If budget is mentioned, convert it into an approximate nightly hotel budget.
- Mention hotel type if obvious (budget, luxury, hostel, family, honeymoon).
- Keep the query under 20 words.
- Return ONLY the search query.

Examples:

Trip from Delhi to Tokyo
→ Best hotels in Tokyo Japan

Trip from Mumbai to Singapore
→ Best hotels in Singapore

7 day Vietnam trip under ₹60000
→ Budget hotels in Hanoi under ₹2500 per night

Backpacking Bali
→ Budget hostels in Bali

Family trip to Kerala
→ Family friendly hotels in Munnar
"""
),
("human","{query}")
])
hotel_search_chain = hotel_search_prompt | llm

#Hotel Agent    
def hotel_agent(state: TravelState) -> TravelState:
    hotel_query = hotel_search_chain.invoke({"query": state["user_query"]}).content.strip()

    hotel_data = tavily_search(
        hotel_query,
        hotel_domains=[
            "booking.com",
            "agoda.com",
            "tripadvisor.com",
            "hotels.com",
            "hostelworld.com",
        ],
    )

    return {
        "hotel_results": hotel_data,
        "messages": [AIMessage(content=f"Hotel information fetched using query: {hotel_query}")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


#Itinerary Agent
def itinerary_agent(state: TravelState) -> TravelState:
    prompt=f"""Create a complete itenary. 
User Query: 
{state['user_query']}. 

Flight Results:
{state['flight_results']}. 

Hotel Results: 
{state['hotel_results']} 

Make the itenary practical, budget aware and easy to follow.
"""

    response=llm.invoke([
        SystemMessage(content="You are a travel agent. You will be provided with user prompt, flight results and hotel results. Your task is to create a complete itenary for the user."),
        HumanMessage(content=prompt)
    ])
    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

#Final Agent Response
def final_agent(state: TravelState) -> TravelState:
    final_prompt=f"""
Generate a final response for the user based on the following information:
User Query: {state['user_query']}.
Flight Results: {state['flight_results']}.
Hotel Results: {state['hotel_results']}.
Itinerary: {state['itinerary']}.


Format the final answer beautifully as a polished travel itinerary using markdown:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget
6. Final Recommendations

Important:
- Use markdown headings like #, ##, ### for sections.
- Use **bold** for important points and bullet lists for details.
- Keep it clear, practical, and easy to read.
- Keep the response useful for real travel planning.
"""
    response=llm.invoke([
        SystemMessage(content="You are a professional AI travel agent."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages":[response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

graph=StateGraph(TravelState)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)

#Postgres Checkpointer
DATABASE_URL=get_database_url()
_conn=psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
checkpointer=PostgresSaver(_conn)
checkpointer.setup()
travel_graph=graph.compile(checkpointer=checkpointer)

#Function for FastAPI
def run_travel_agent(user_input: str, thread_id: str | None= None):
    if not thread_id:
        thread_id=f"user_{uuid.uuid4().hex}"
    
    config ={
        "configurable":{
            "thread_id": thread_id
        }
    }
    result=travel_graph.invoke(
        {
        "messages": [HumanMessage(content=user_input)],
        "user_query": user_input,
        "flight_results": "",
        "hotel_results": "",
        "itinerary": "",
        "llm_calls": 0
        },
    config=config
    )
    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }