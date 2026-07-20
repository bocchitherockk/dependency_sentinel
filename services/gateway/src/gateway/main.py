from fastapi import FastAPI
import uvicorn
import requests

from common.config import services
from common.schemas.CloneRepositoryRequest import CloneRepositoryRequest

app = FastAPI()


@app.post("/scan_repository")
def scan_repository(clone_repository_request: CloneRepositoryRequest):
    repository_url = clone_repository_request.repository_url
    # Call the repository storage service to clone the repository
    response = requests.post(
        f'{services['repository-storage-service']['endpoint']}/clone_repository',
        json={"repository_url": repository_url}
    )
    if response.status_code != 200:
        return {"error": "Failed to clone repository"}

    # Call the repository storage service to get the list of files and directories in the repository
    response = requests.get(
        f"{services['repository-storage-service']['endpoint']}/repositories/{repository_url.split('/')[-1].replace('.git', '')}",
        params={"display_files_content": False}
    )
    if response.status_code != 200:
        return {"error": "Failed to get repository content"}

    return response.json()

def main():
    uvicorn.run(
        app,
        host=services['gateway']['host'],
        port=services['gateway']['port'],
    )