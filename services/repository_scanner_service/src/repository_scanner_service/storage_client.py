import httpx


STORAGE_URL = "http://127.0.0.1:8001"


def get_repository_content(path: str, show_content: bool = False):
    response = httpx.get(
        f"{STORAGE_URL}/repositories/{path}",
        params={
            "display_files_content": show_content
        },
    )

    response.raise_for_status()

    return response.json()