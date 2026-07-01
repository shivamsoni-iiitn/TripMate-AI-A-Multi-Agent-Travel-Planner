from tavily import TavilyClient
import os
from dotenv import load_dotenv

load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def tavily_search(query, max_results=5, min_score=0.3, hotel_domains=None):
    response = client.search(
        query=query,
        max_results=max_results,
        include_domains=hotel_domains, # e.g. ["booking.com", "tripadvisor.com"]
    )

    result = []
    for i, r in enumerate(response['results'], 1):
        if r.get('score', 1) < min_score:
            continue
        title = r.get('title', 'Unknown')
        url = r.get('url', '')
        snippet = r.get('content', '').strip()
        if len(snippet) > 300:
            snippet = snippet[:300].rsplit(" ", 1)[0] + "..."
        result.append(f"{i}. {title}\n{url}\n{snippet}\n")

    return "\n\n".join(result) if result else "No strong hotel matches found."