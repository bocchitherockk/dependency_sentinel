import os
from pathlib import Path
from fastapi import FastAPI
import uvicorn
from git import Repo

from repository_storage_service.utils import get_fs_object_content



app = FastAPI()

os.chdir('./services/repository_storage_service/') # change current working directory
os.makedirs('./repositories', exist_ok=True)

# This endpoint should be called only by the scheduler service, which will provide the repository URL to be cloned.
# The scheduler service will be responsible for managing the list of repositories to be cloned and for calling this endpoint with the appropriate repository URL.
# For now this is a get endpoint that takes the repository URL as a query parameter, but in the future it should be a post endpoint that takes the repository URL in the request body.
@app.get('/clone')
def clone_repository(repository_url: str):
    destination = './repositories/' + repository_url.split('/')[-1].replace('.git', '')
    if Path(destination).exists():
        # fetch the latest changes if the repository already exists
        repo = Repo(destination)
        origin = repo.remotes.origin
        origin.pull()
        return {
            'message': f'Repository {repository_url} already exists. Pulled the latest changes.'
        }
    else:
        Repo.clone_from(repository_url, destination)
        return {
            'message': f'Repository {repository_url} cloned successfully.'
        }

# This endpoint should be called by the repository scanner service (with display_files_content set to False) to get the list of files and directories in the repository to then use them to talk to the LLM and get the important manifest files in the repository.
# This endpoint should also be called by the dependency analyzer service (with display_files_content set to True) to get the content of the important manifest files in the repository to then parse them and get the dependencies in the repository.
# This endpoint might be called by the dependency modifier service (with display_files_content set to True) to get the content of the important manifest files in the repository to then modify them and write them back to the repository. (i might also remove the Dependency modifier service and let this Repository storage service handle the modification directly through the MCP call)
@app.get('/repositories/{path:path}')
def get_fs_object_content(path: str, display_files_content: bool = False):
    fs_object_path = Path(f'./repositories/{path}')
    if not fs_object_path.exists():
        return { 'error': 'File or directory not found' }

    fs_object_content = get_fs_object_content(fs_object_path, display_files_content)
    return fs_object_content


# This endpoint should be called by the Dependency modifier service (which is initially called by the LLM through the MCP server)
# note: the Dependency modifier service will be responsible for providing correct content to be written in the file
@app.put('/repositories/{path:path}')
def update_file_content(path: str, new_content: str):
    file_path = Path(f'./repositories/{path}')
    if not file_path.exists():
        return { 'error': 'File not found' }

    with open(file_path, 'w') as f:
        f.write(new_content)

    return { 'message': f'File {path} updated successfully.' }

def main() -> None:
    uvicorn.run(
        app,
        host='127.0.0.1',
        port=8000,
        # reload=True,
    )
