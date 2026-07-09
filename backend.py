import os 
import certifi
from dotenv import load_dotenv
import warnings
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
from langchain_core.prompts import ChatPromptTemplate

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic"
)

os.environ['SSL_CERT_FILE'] = certifi.where()   
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

load_dotenv()

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
    # Conversation
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    origin: str | None
    destination: str | None
    departure_date: str | None
    return_date: str | None
    budget: int | None
    travelers: int | None
    trip_days: int | None
    hotel_type: str | None
    transport_preference: str | None
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int

from pydantic import BaseModel

class TripContext(BaseModel):
    origin: str | None = None
    destination: str | None = None
    departure_date: str | None = None
    return_date: str | None = None
    budget: int | None = None
    travelers: int | None = None
    trip_days: int | None = None
    hotel_type: str | None = None
    transport_preference: str | None = None

structured_context_llm = llm.with_structured_output(TripContext)

context_prompt = ChatPromptTemplate.from_messages([(
"system",
"""
You are a travel context extractor.

Extract ONLY the fields explicitly mentioned or that can be confidently inferred.

Rules:

- Preserve previous values if the user doesn't change them.
- If user says "make it luxury", only update hotel_type.
- If user says "increase budget to 80000", only update budget.
- If user says "change destination to Osaka", only update destination.
- Never overwrite existing values with null.
- Infer origin, destination, trip duration, budget, travelers, hotel type, and transport preference whenever clearly mentioned.
- Never erase previous values.
- Only update fields the user changes.
- Return ONLY structured output.
"""
),
(
"human",
"""
Conversation History:
{history}

Previous Context:

Origin: {origin}
Destination: {destination}
Departure Date: {departure_date}
Return Date: {return_date}
Budget: {budget}
Travelers: {travelers}
Trip Days: {trip_days}
Hotel Type: {hotel_type}
Transport Preference: {transport_preference}

Current User Request:

{query}
"""
)
])

context_chain = context_prompt | structured_context_llm


def context_agent(state: TravelState):
    history = "\n".join(
        m.content
        for m in state.get("messages", [])[-6:]
        if hasattr(m, "content")
    )
    context = context_chain.invoke({
        "origin": state.get("origin"),
        "destination": state.get("destination"),
        "departure_date": state.get("departure_date"),
        "return_date": state.get("return_date"),
        "budget": state.get("budget"),
        "travelers": state.get("travelers"),
        "trip_days": state.get("trip_days"),
        "hotel_type": state.get("hotel_type"),
        "transport_preference": state.get("transport_preference"),
        "history": history,
        "query": state.get("user_query")
    })

    return {

        "origin": context.origin or state.get("origin"),

        "destination": context.destination or state.get("destination"),

        "departure_date": context.departure_date or state.get("departure_date"),

        "return_date": context.return_date or state.get("return_date"),

        "budget": context.budget if context.budget is not None else state.get("budget"),

        "travelers": context.travelers or state.get("travelers"),

        "trip_days": context.trip_days or state.get("trip_days"),

        "hotel_type": context.hotel_type or state.get("hotel_type"),

        "transport_preference":
            context.transport_preference
            or state.get("transport_preference"),

        "messages":[
            AIMessage(content="Trip context updated.")
        ],

        "llm_calls": state.get("llm_calls", 0)+1
    }



#Flight Agent
def flight_agent(state: TravelState) -> TravelState:
    if not state.get("destination"):
        return {"flight_results": "Destination not provided."}
    flight_data = search_flights(origin=state.get("origin"),destination=state.get("destination"))
    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


#Hotel Agent    
def hotel_agent(state: TravelState) -> TravelState:
    hotel_query = f"""
    Best {state.get("hotel_type") or ""} hotels in
    {state.get("destination")}

    Budget:
    {state.get("budget")}
"""
    
    if not state.get("destination"):
        return {
        "hotel_results": "Destination not provided.",
        "messages": [AIMessage(content="Hotel search skipped.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
        }
    else:
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
    prompt=f"""Create a complete itinerary. 
Origin:
{state.get('origin')}

Destination:
{state.get('destination')}

Budget:
{state.get('budget')}

Trip Days:
{state.get('trip_days')}

Travellers:
{state.get('travelers')}

Current Request:
{state.get('user_query')}

Flight Results:
{state.get('flight_results')}. 

Hotel Results: 
{state.get('hotel_results')} 

Make the itenary practical, budget aware and easy to follow.
"""

    response=llm.invoke([
        SystemMessage(content="You are a travel agent. You will be provided with user prompt, flight results and hotel results. Your task is to create a complete itenary for the user."),
        *state.get("messages", []),
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
Origin: {state.get("origin")}

Destination: {state.get("destination")}

Departure Date: {state.get("departure_date")}

Return Date: {state.get("return_date")}

Budget: {state.get("budget")}

Travelers: {state.get("travelers")}

Trip Days: {state.get("trip_days")}

Hotel Type: {state.get("hotel_type")}

Current User Request:
{state.get("user_query")}
Flight Results: {state.get('flight_results')}.
Hotel Results: {state.get('hotel_results')}.
Itinerary: {state.get('itinerary')}.


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
        *state.get("messages", []),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages":[response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

graph=StateGraph(TravelState)
graph.add_node("context_agent", context_agent)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START,"context_agent")
graph.add_edge("context_agent","flight_agent")
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

DEFAULT_STATE = {
    "messages": [],

    "user_query": "",

    "origin": None,
    "destination": None,

    "departure_date": None,
    "return_date": None,

    "budget": None,

    "travelers": 1,

    "trip_days": None,

    "hotel_type": None,

    "transport_preference": None,

    "flight_results": "",

    "hotel_results": "",

    "itinerary": "",

    "llm_calls": 0,
}

#Function for FastAPI
def run_travel_agent(user_input: str, thread_id: str | None = None):

    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # Fetch previous state if it exists
    previous_state = travel_graph.get_state(config)

    if previous_state.values:

        # Only send the incremental update. The checkpointer already
        # holds everything else (origin, destination, budget, etc.);
        # re-sending the full old message list here would cause
        # operator.add to duplicate the entire conversation history
        # on every turn.
        state = {
            "messages": [HumanMessage(content=user_input)],
            "user_query": user_input,
        }

    else:

        state = {
            "messages":[HumanMessage(content=user_input)],
            "user_query":user_input,
            "origin":None,
            "destination":None,
            "departure_date":None,
            "return_date":None,
            "budget":None,
            "travelers":1,
            "trip_days":None,
            "hotel_type":None,
            "transport_preference":None,
            "flight_results":"",
            "hotel_results":"",
            "itinerary":"",
            "llm_calls":0
        }

    result = travel_graph.invoke(
        state,
        config=config
    )

    return {
        "thread_id":thread_id,
        "answer":result["messages"][-1].content,
        "flight_results":result.get("flight_results",""),
        "hotel_results":result.get("hotel_results",""),
        "itinerary":result.get("itinerary",""),
        "llm_calls":result.get("llm_calls",0)
    }