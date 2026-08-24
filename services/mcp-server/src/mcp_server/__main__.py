from logging import getLogger
from common.logging.global_logger import get_global_logger

logger = get_global_logger(__name__)
logger.info('Starting MCP Server...')

from mcp_server.main import main as mcp_server_main

def main():
    mcp_server_main()
