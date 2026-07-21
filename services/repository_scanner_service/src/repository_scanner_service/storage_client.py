import httpx
from common.config import services

def get_repository_content(path: str, show_content: bool = False):
    response = httpx.get(
        f"{services['repository-storage-service']['endpoint']}/repositories/{path}",
        params={
            "display_files_content": show_content
        },
    )

    response.raise_for_status()
    return response.json()