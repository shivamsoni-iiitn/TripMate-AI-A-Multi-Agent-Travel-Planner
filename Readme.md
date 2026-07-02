# ✈️ TripMate AI — A Multi-Agent Travel Planner with LangGraph

An open-source AI travel planner that turns a natural-language trip request into a practical travel plan with flight suggestions, hotel recommendations, and a day-by-day itinerary. The project uses a multi-agent workflow built with LangGraph, LangChain, OpenAI, and FastAPI.

## Why this project?

Planning a trip usually means jumping between multiple websites, tools, and spreadsheets. This project brings that flow into one experience by combining:

- a flight-search agent,
- a hotel-recommendation agent,
- an itinerary-planning agent, and
- a final response agent,

all coordinated through a LangGraph workflow.

Unlike traditional rule-based systems, TripMate AI uses **OpenAI Structured Outputs** to understand natural-language travel requests and extract structured travel information such as departure airport, destination airport, and trip details before querying external APIs.

## Features

- ✈️ Flight research using AviationStack
- 🏨 Hotel suggestions using Tavily Search
- 🧠 LLM-powered travel query understanding using OpenAI Structured Outputs
- 📝 AI-generated travel itineraries
- 🧩 Multi-agent orchestration with LangGraph
- 🌐 FastAPI backend with a simple web interface
- 💾 Conversation state persistence using PostgreSQL
- ⚡ LLM-powered responses using OpenAI GPT-5 Nano

## Tech Stack

- Python 3.10+
- FastAPI
- Jinja2 + HTML/CSS/JavaScript frontend
- LangGraph
- LangChain
- OpenAI GPT-5 Nano
- PostgreSQL
- Tavily API
- AviationStack API

## Project Structure

```text
.
├── app.py                # FastAPI app entry point
├── backend.py            # LangGraph travel workflow
├── requirements.txt      # Python dependencies
├── static/               # Static frontend assets
├── templates/            # HTML templates
└── tools/                # Flight and web search integrations
```

## Prerequisites

Before running the project locally, make sure you have:

- Python 3.10 or newer installed
- PostgreSQL running and accessible
- API keys for:
  - OpenAI
  - Tavily
  - AviationStack

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/travel_db
OPENAI_API_KEY=your_openai_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
TAVILY_API_KEY=your_tavily_api_key
DEFAULT_ORIGIN_IATA=DEL
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the App

Start the FastAPI server:

```bash
python app.py
```

Then open your browser at:

```text
http://127.0.0.1:8000/
```

## API Endpoints

- GET /health - Health check
- POST /api/travel - Submit a travel request

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/travel \
  -H "Content-Type: application/json" \
  -d '{"message":"Plan a 3-day trip to Tokyo with a budget of $1200"}'
```

## How the Workflow Works

1. The user submits a travel request.
2. The Flight Agent uses an LLM to understand the query, extract airport information, and fetch live flight data.
3. The Hotel Agent generates an optimized hotel search query using an LLM and retrieves hotel recommendations through Tavily Search.
4. The Itinerary Agent combines the user request, flight details, and hotel recommendations to generate a travel itinerary.
5. The Final Agent formats everything into a complete travel plan.


## Acknowledgments

This project demonstrates how **LangGraph**, **OpenAI Structured Outputs**, and external travel APIs can be combined to build a practical multi-agent AI travel planning application.