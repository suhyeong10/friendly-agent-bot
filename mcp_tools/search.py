import os
import logging
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

from langchain_community.tools.tavily_search import TavilySearchResults
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY")

mcp = FastMCP(
    "Search",
    instructions="You are a search engine. You can search for any information on the web.",
    host="0.0.0.0",
    port=8005
)


search = TavilySearchResults(k=5)

@mcp.tool()
def search_tool(query: str):
    """
    Returns the search result from the Tavily Search API based on the user's query. 
    This tool can be used to search for get information from the web.
    Never use this tool to search for places or songs.

    Args:
        query: the keyword or phrase for web search. query is must be korean.
    """
    result = search.invoke(query)
    result = "\n".join([item["content"] for item in result if "content" in item])

    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
