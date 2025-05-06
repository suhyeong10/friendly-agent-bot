import os
import asyncio
import logging
import requests
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "NaverPlace",
    instructions="You are a get place information from NAVER Place API.",
    host="0.0.0.0",
    port=8006
)

NAVER_PLACE_API_URL = "https://openapi.naver.com/v1/search/local.json"
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")
NAVER_PLACE_API_URL = "https://openapi.naver.com/v1/search/local.json"

def clean_text(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "").strip()


def search_naver_places(query: str, display: int = 5) -> list:
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }

    logger = logging.getLogger(__name__)
    logger.info(f"[🔍 NAVER 장소 검색 시작] 쿼리: {query}")

    params = {
        "query": query,
        "display": display,
        "start": 1,
        "sort": "comment"
    }

    try:
        response = requests.get(NAVER_PLACE_API_URL, headers=headers, params=params)
        logger.info("HTTP 요청 성공, response 받음")
    except Exception as e:
        logger.error(f"[❗HTTP 요청 실패] {e}")
        return

    if response.status_code != 200:
        logger.error(f"Naver API error: {response.status_code}")
        return

    try:
        data = response.json()
        logger.info(f"네이버 응답 데이터: {data}")
    except ValueError as e:
        logger.error(f"[❗JSON 파싱 실패] {e}")
        return

    items = data.get("items", [])

    if not items:
        logger.error(f"[❗Naver 장소 검색 실패] 쿼리: {query} → {response.status_code}")
        return

    results = []
    for item in items:
        result = {
            "name": clean_text(item.get("title", "")),
            "address": item.get("address", ""),
            "category": item.get("category", ""),
            "link": item.get("link", ""),
            "description": clean_text(item.get("description", ""))
        }
        results.append(result)

    logger.info(f'[🔍 NAVER 장소 결과] {results}')

    return results

@mcp.tool()
def get_naver_place_tool(query: str) -> list:
    """
    Returns a list of recommended places from NAVER Place API based on the user's search query.

    Args:
        query: the keyword or phrase to search for relevant places using NAVER. query is must be korean.
    """
    result = search_naver_places(query, display=5)
    result = '\n'.join([
        f"이름: {item['name']}, 주소: {item['address']}, 카테고리: {item['category']}, 링크: {item['link']}, 설명: {item['description']}" for item in result
    ])

    return result

if __name__ == "__main__":
    mcp.run(transport="stdio")
