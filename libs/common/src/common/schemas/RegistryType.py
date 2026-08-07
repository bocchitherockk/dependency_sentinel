from enum import Enum

class RegistryType(str, Enum):
    PYPI = "PyPI"
    NPM = "npm"
    MAVEN = "Maven"
    DOCKERHUB = "Docker Hub"
    LIBRARIES_IO = "Libraries.io"
    PRIVATE = "Private Registry"
