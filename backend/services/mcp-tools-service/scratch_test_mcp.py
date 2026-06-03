import asyncio
import json
import os
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def test_mcp_read():
    # Points to your local mcp-tools-service
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "main.py"],
        cwd=r"c:\Users\BandiPreethamReddy\Desktop\Tagent\backend\services\mcp-tools-service"
    )

    print("--- Connecting to MCP Tools Service ---")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 1. List tools to make sure everything is registered
            print("\n1. Listing available tools:")
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                print(f" - {tool.name}: {tool.description}")

            # 2. Try a read operation (get_user_info)
            print("\n2. Attempting 'get_user_info'...")
            try:
                result = await session.call_tool("get_user_info", arguments={})
                print(f"Response: {result.content[0].text if result.content else 'No text content'}")
            except Exception as e:
                print(f"Error calling tool: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_read())
