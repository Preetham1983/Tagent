import asyncio
import httpx
from tagent.mcp.tools._token import get_graph_token

async def test():
    token = await get_graph_token()
    async with httpx.AsyncClient() as http:
        email = 'j_raasrith@epam.com'
        r = await http.get('https://graph.microsoft.com/v1.0/users', headers={'Authorization': f'Bearer {token}'}, params={'$filter': f'mail eq \'{email}\' or userPrincipalName eq \'{email}\'', '$select': 'id,displayName,mail,userPrincipalName'})
        print('EQ Filter:', r.json())
        
if __name__ == '__main__':
    asyncio.run(test())
