import sys

import chromadb
import ollama

from config import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL, QUERY_PREFIX

TOP_K = 5  # how many chunks to return

# Make sure special characters (bullets, diameter signs) print correctly in PowerShell.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_collection():
    """Open the saved ChromaDB collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION_NAME)


def search(question: str, top_k: int = TOP_K, collection=None) -> list[dict]:
    """Find the chunks whose meaning is closest to the question."""
    if collection is None:
        collection = get_collection()

    response = ollama.embed(model=EMBED_MODEL, input=QUERY_PREFIX + question)
    query_vector = response["embeddings"][0]

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    texts = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    hits = []
    for text, meta, distance in zip(texts, metas, distances):
        hits.append(
            {
                "source": meta["source"],
                "page": meta["page"],
                "chunk": meta["chunk"],
                "text": text,
                # Chroma returns cosine distance; 1 - distance = similarity.
                # Closer to 1 means more similar in meaning.
                "score": round(1 - distance, 3),
            }
        )
    return hits


def show_hits(hits: list[dict]) -> None:
    """Print the search results in a readable way."""
    for rank, hit in enumerate(hits, start=1):
        short_name = hit["source"].replace("Atlas_AI_", "").replace(".pdf", "")
        print(f"\n#{rank}  score={hit['score']}  {short_name}  page {hit['page']}")
        print("    " + hit["text"][:160] + "...")


def main() -> None:
    collection = get_collection()
    print(f"Connected. {collection.count()} chunks in the database.")
    print("Type a question, or q to quit.")

    while True:
        question = input("\nQuestion> ").strip()
        if question.lower() in ("q", "quit", "exit"):
            break
        if not question:
            continue
        try:
            show_hits(search(question, collection=collection))
        except Exception as error:
            print(f"Search failed: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()