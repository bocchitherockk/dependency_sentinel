from pathlib import Path

def _get_file_content(file_path: Path, display_content: bool = False):
    file_info = {
        'repository_name': file_path.parts[1],
        'type': 'file',
        'name': file_path.name,
        'path': str(file_path)
    }
    if display_content:
        with open(file_path, 'r') as f:
            file_info['content'] = f.read()
    return file_info

def _get_directory_content(directory_path: Path, display_files_content: bool = False):
    content = []
    for fs_object in directory_path.iterdir():
        if fs_object.is_dir():
            content.append({
                'repository_name': fs_object.parts[1],
                'type': 'directory',
                'name': fs_object.name,
                'path': str(fs_object),
                'content': _get_directory_content(fs_object, display_files_content)
            })
        else:
            content.append(_get_file_content(fs_object, display_files_content))
    return content

def get_fs_object_content(fs_object_path: Path, display_files_content: bool = False):
    if fs_object_path.is_dir():
        return _get_directory_content(fs_object_path, display_files_content)
    else:
        return _get_file_content(fs_object_path, display_files_content)