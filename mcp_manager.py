import asyncio
import json
from typing import Dict, Any

from langchain_mcp_adapters.client import MultiServerMCPClient


DEFAULT_MCP_CONFIG = {
    "mcpServers": {}
}


def load_mcp_config() -> Dict[str, Any]:
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        
        return config["mcpServers"]
    except FileNotFoundError:
        return DEFAULT_MCP_CONFIG
    
async def cleanup_mcp_client(client=None):
    if client is not None:
        try:
            # Direct call instead of using shield
            await client.__aexit__(None, None, None)
        except asyncio.CancelledError:
            # Ignore CancelledError during cleanup
            pass
        except Exception as e:
            print(f"Error occurred while cleaning up MCP client: {str(e)}")


async def init_mcp_client():
    mcp_config = load_mcp_config()

    try:
        client = MultiServerMCPClient(
            mcp_config
        )
        await client.__aenter__()

        tools = client.get_tools()

        return client, tools
    except Exception as e:
        print(f"Error occurred while initializing MCP client: {str(e)}")

        if "client" in locals():
            await cleanup_mcp_client(client)
        raise