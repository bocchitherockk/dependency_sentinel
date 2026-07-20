import json
import xml.etree.ElementTree as ET


def parse_package_json(content: str):
    data = json.loads(content)

    dependencies = []

    for name, version in data.get("dependencies", {}).items():
        dependencies.append({
            "name": name,
            "version": version,
        })

    return {
        "type": "npm",
        "dependencies": dependencies,
    }


def parse_pom_xml(content: str):
    root = ET.fromstring(content)

    dependencies = []

    for dependency in root.findall(".//{*}dependency"):
        group_id = dependency.findtext("{*}groupId")
        artifact_id = dependency.findtext("{*}artifactId")
        version = dependency.findtext("{*}version")

        dependencies.append({
            "name": f"{group_id}:{artifact_id}",
            "version": version,
        })

    return {
        "type": "maven",
        "dependencies": dependencies,
    }


def parse_manifest(path: str, content: str):
    if path.endswith("package.json"):
        return parse_package_json(content)

    if path.endswith("pom.xml"):
        return parse_pom_xml(content)

    return {
        "type": "unknown",
        "dependencies": [],
    }