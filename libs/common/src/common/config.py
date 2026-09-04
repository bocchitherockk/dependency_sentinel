import os
from logging import Logger

from dotenv import load_dotenv

from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)

load_dotenv()
logger.info("Environment variables loaded from .env file.")
logger.debug("Environment variables:")
logger.debug(f'    USE_DOCKER:                         {os.getenv("USE_DOCKER")}')
logger.debug(f'    SCHEDULER_PORT:                     {os.getenv("SCHEDULER_PORT")}')
logger.debug(f'    GATEWAY_PORT:                       {os.getenv("GATEWAY_PORT")}')
logger.debug(f'    REPOSITORY_STORAGE_SERVICE_PORT:    {os.getenv("REPOSITORY_STORAGE_SERVICE_PORT")}')
logger.debug(f'    REPOSITORY_SCANNER_SERVICE_PORT:    {os.getenv("REPOSITORY_SCANNER_SERVICE_PORT")}')
logger.debug(f'    LLM_SERVICE_PORT:                   {os.getenv("LLM_SERVICE_PORT")}')
logger.debug(f'    REGISTRY_SERVICE_PORT:              {os.getenv("REGISTRY_SERVICE_PORT")}')
logger.debug(f'    MCP_SERVER_PORT:                    {os.getenv("MCP_SERVER_PORT")}')
logger.debug(f'    SECURITY_INTELLIGENCE_SERVICE_PORT: {os.getenv("SECURITY_INTELLIGENCE_SERVICE_PORT")}')


services = {
    'scheduler': {
        'bind_host': '0.0.0.0',
        'docker_host': 'scheduler',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('SCHEDULER_PORT')),
        'endpoint': None,
    },
    'gateway': {
        'bind_host': '0.0.0.0',
        'docker_host': 'gateway',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('GATEWAY_PORT')),
        'endpoint': None,
    },
    'repository-storage-service': {
        'bind_host': '0.0.0.0',
        'docker_host': 'repository-storage-service',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('REPOSITORY_STORAGE_SERVICE_PORT')),
        'endpoint': None,
    },
    'repository-scanner-service': {
        'bind_host': '0.0.0.0',
        'docker_host': 'repository-scanner-service',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('REPOSITORY_SCANNER_SERVICE_PORT')),
        'endpoint': None,
    },
    'llm-service': {
        'bind_host': '0.0.0.0',
        'docker_host': 'llm-service',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('LLM_SERVICE_PORT')),
        'endpoint': None,
    },
    'registry-service': {
        'bind_host': '0.0.0.0',
        'docker_host': 'registry-service',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('REGISTRY_SERVICE_PORT')),
        'endpoint': None,
    },
    'mcp-server': {
        'bind_host': '0.0.0.0',
        'docker_host': 'mcp-server',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('MCP_SERVER_PORT')),
        'endpoint': None,
    },
    'security-intelligence-service': {
        'bind_host': '0.0.0.0',
        'docker_host': 'security-intelligence-service',
        'loopback_host': '127.0.0.1',
        'port': int(os.getenv('SECURITY_INTELLIGENCE_SERVICE_PORT')),
        'endpoint': None,
    },
}

use_docker: bool = os.getenv('USE_DOCKER', 'false') == 'true'

for config in services.values():
    host: str = config['docker_host'] if use_docker else config['loopback_host']
    port: str = config['port']
    config['endpoint'] = f'http://{host}:{port}'

logger.info(f"Service endpoints configured.")
logger.debug(f"Service endpoints: { {service: config['endpoint'] for service, config in services.items()} }")
