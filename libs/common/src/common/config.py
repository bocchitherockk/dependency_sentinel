import os

def get_service_config(service_name: str, default_port: int):
    bind_host = os.getenv("BIND_HOST", "127.0.0.1")
    env_var_name = f"{service_name.upper().replace('-', '_')}_HOST"
    endpoint_host = os.getenv(env_var_name, "127.0.0.1")
    
    return {
        'host': bind_host,
        'port': default_port,
        'endpoint': f"http://{endpoint_host}:{default_port}"
    }

services = {
    'scheduler': get_service_config('scheduler', 8000),
    'gateway': get_service_config('gateway', 8001),
    'repository-storage-service': get_service_config('repository-storage-service', 8002),
    'repository-scanner-service': get_service_config('repository-scanner-service', 8003),
    'llm-service': get_service_config('llm-service', 8004),
    'registry-service': get_service_config('registry-service', 8005),
    'mcp-server': get_service_config('mcp-server', 8006),
    'security-intelligence-service': get_service_config('security-intelligence-service', 8007),
}