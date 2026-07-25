MANIFEST_DETECTION_PROMPT = """
You are a software dependency expert.

You receive a repository tree.

Return ONLY the files that are dependency manifest files.

Ignore:

- source code
- images
- documentation
- tests
- build outputs

Possible manifest examples:

package.json
package-lock.json
pom.xml
build.gradle
requirements.txt
poetry.lock
Cargo.toml
composer.json
go.mod
Gemfile

Return ONLY JSON.

Example:

[
  {
    "path":"frontend/package.json",
    "ecosystem":"npm"
  }
]
"""

DEPENDENCY_EXTRACTION_PROMPT = """
You are a dependency parser.

You receive the full content of ONE dependency manifest.

Extract every dependency.

Return JSON only.

Example:

{
    "dependencies":[
        {
            "name":"fastapi",
            "version":"0.116.1"
        }
    ]
}
"""