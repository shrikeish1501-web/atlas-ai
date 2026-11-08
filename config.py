from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

COLLECTION_NAME = "atlas_docs"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen3:4b"

# nomic-embed-text works best when text is labelled with its job.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "