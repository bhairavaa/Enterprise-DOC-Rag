import os

# nltk's CWD-import-hijack guard (CWE-427 mitigation) false-positives in this
# project: our venv lives at backend/.venv, so when cwd is the backend/
# directory, nltk's own dependency (regex) resolves to a path *inside* cwd
# and gets misidentified as a hijack attempt. Disabling is safe here since
# the venv is our own trusted install, not an untrusted CWD. Must be set
# before nltk's first (lazy, deep inside SentenceSplitter) import.
os.environ.setdefault("NLTK_DISABLE_IMPORT_SECURITY", "1")
