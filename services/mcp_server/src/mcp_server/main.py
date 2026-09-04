from mcp.server.fastmcp import FastMCP
import httpx
from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.config import services

logger: Logger = get_global_logger(__name__)

mcp_server = FastMCP(
    name='dependency-sentinel',
    host=services['mcp-server']['bind_host'],
    port=services['mcp-server']['port'],
)

logger.info(f"MCP tool 'modify_file' initialized")

@mcp_server.tool(title='Modify File', description='Replaces the content of a file with new content.')
async def modify_file(file_path: str, new_content: str):
    logger.info(f'Received request to modify file: {file_path}')
    logger.debug(f'New content: {new_content}')
    url: str = f'{services['repository-storage-service']['endpoint']}/repositories/{file_path}'
    update_file_content_request: UpdateFileContentRequest = UpdateFileContentRequest(
        new_content=new_content
    )
    async with httpx.AsyncClient() as client:
        response = await client.put(
            url,
            json=update_file_content_request.model_dump(mode='json'),
        )
        response.raise_for_status()
        logger.info(f'Successfully modified file: {file_path}')
        return response.json()


def main():
    mcp_server.run(transport='streamable-http')
