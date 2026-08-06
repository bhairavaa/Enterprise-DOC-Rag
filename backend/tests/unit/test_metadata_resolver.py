import json

from app.ingestion.metadata_resolver import MetadataResolver


def test_resolves_tenant_department_doc_type_from_folder_path(tmp_path):
    file_path = tmp_path / "acme" / "engineering" / "policies" / "handbook.pdf"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    resolver = MetadataResolver(tmp_path)
    meta = resolver.resolve(file_path)

    assert meta.tenant_id == "acme"
    assert meta.department == "engineering"
    assert meta.doc_type == "policies"
    assert meta.tags == []


def test_defaults_tenant_id_when_file_is_at_root(tmp_path):
    file_path = tmp_path / "handbook.pdf"
    file_path.touch()

    resolver = MetadataResolver(tmp_path)
    meta = resolver.resolve(file_path)

    assert meta.tenant_id == "default"
    assert meta.department is None
    assert meta.doc_type is None


def test_manifest_overrides_take_precedence_over_folder_path(tmp_path):
    file_path = tmp_path / "acme" / "engineering" / "policies" / "handbook.pdf"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    manifest = {
        "acme/engineering/policies/handbook.pdf": {
            "doc_type": "employee_handbook",
            "tags": ["hr", "onboarding"],
        }
    }
    (tmp_path / "_meta.json").write_text(json.dumps(manifest), encoding="utf-8")

    resolver = MetadataResolver(tmp_path)
    meta = resolver.resolve(file_path)

    assert meta.tenant_id == "acme"
    assert meta.department == "engineering"
    assert meta.doc_type == "employee_handbook"
    assert meta.tags == ["hr", "onboarding"]


def test_missing_manifest_is_not_an_error(tmp_path):
    file_path = tmp_path / "acme" / "handbook.pdf"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    resolver = MetadataResolver(tmp_path)
    meta = resolver.resolve(file_path)

    assert meta.tenant_id == "acme"
