import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedMetadata:
    tenant_id: str
    department: str | None
    doc_type: str | None
    tags: list[str]


class MetadataResolver:
    """Resolves per-file metadata from a folder-path convention, with an
    optional manifest.json for overrides/additions.

    Convention: <root>/<tenant_id>/<department>/<doc_type>/<file>. Shorter
    paths simply leave department/doc_type unset. A `_meta.json` at the root
    of the ingestion run maps a POSIX-style path (relative to root) to
    overrides, e.g.:

        {"engineering/policies/handbook.pdf": {"tags": ["hr", "onboarding"]}}

    Manifest values always take precedence over folder-derived values.
    """

    MANIFEST_FILENAME = "_meta.json"

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self._manifest = self._load_manifest(root_dir)

    @staticmethod
    def _load_manifest(root_dir: Path) -> dict[str, dict]:
        manifest_path = root_dir / MetadataResolver.MANIFEST_FILENAME
        if not manifest_path.exists():
            return {}
        with manifest_path.open(encoding="utf-8") as f:
            return json.load(f)

    def resolve(self, file_path: Path) -> ResolvedMetadata:
        relative = file_path.relative_to(self.root_dir)
        parts = relative.parts[:-1]  # drop the filename itself

        tenant_id = parts[0] if len(parts) >= 1 else "default"
        department = parts[1] if len(parts) >= 2 else None
        doc_type = parts[2] if len(parts) >= 3 else None
        tags: list[str] = []

        override = self._manifest.get(relative.as_posix(), {})
        tenant_id = override.get("tenant_id", tenant_id)
        department = override.get("department", department)
        doc_type = override.get("doc_type", doc_type)
        tags = override.get("tags", tags)

        return ResolvedMetadata(
            tenant_id=tenant_id, department=department, doc_type=doc_type, tags=tags
        )
