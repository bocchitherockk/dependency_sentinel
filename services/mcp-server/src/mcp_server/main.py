from mcp.server.fastmcp import FastMCP
import httpx

from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.config import services

mcp_server = FastMCP(
    name='dependency-sentinel',
    host=services['mcp-server']['host'],
    port=services['mcp-server']['port'],
)

@mcp_server.tool(title='Modify File', description='Replaces the content of a file with new content.')
async def modify_file(file_path: str, new_content: str):
    url: str = f'{services['repository-storage-service']['endpoint']}/repositories/{file_path}'
    update_file_content_request: UpdateFileContentRequest = UpdateFileContentRequest(
        new_content=new_content
    )
    async with httpx.AsyncClient() as client:
        response = await client.put(url, json=update_file_content_request)
        response.raise_for_status()
        return response.json()


def main():
    mcp_server.run(transport='streamable-http')
