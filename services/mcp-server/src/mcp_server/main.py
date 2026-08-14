from mcp.server.fastmcp import FastMCP
import httpx

from common.schemas.UpdateFileContentRequest import UpdateFileContentRequest
from common.config import services

mcp_server = FastMCP(
    name='dependency-sentinel',
    host=services['mcp-server']['host'],
    port=services['mcp-server']['port'],
)


def main():
    mcp_server.run(transport='streamable-http')
