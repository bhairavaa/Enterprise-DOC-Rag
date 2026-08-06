from app.ingestion.file_hash import hash_file, stat_file


def test_hash_file_is_deterministic(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello world")

    assert hash_file(path) == hash_file(path)


def test_hash_file_changes_with_content(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello world")
    original = hash_file(path)

    path.write_bytes(b"hello world!!!")
    assert hash_file(path) != original


def test_hash_file_matches_known_sha256(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello world")
    # sha256("hello world")
    assert hash_file(path) == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_stat_file_reflects_size(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"0123456789")

    stat = stat_file(path)
    assert stat.size_bytes == 10
