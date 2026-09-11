import pydantic
from pydantic import BaseModel

from common.schemas.ManifestFile import ManifestFile

fields_to_exclude = {'content'}
filtered_fields = {
    k: (v.annotation, v) 
    for k, v in ManifestFile.model_fields.items() 
    if k not in fields_to_exclude
}

ManifestFileWithoutContent: type[BaseModel] = pydantic.create_model(
    'ManifestFileWithoutContent',
    **filtered_fields
)
