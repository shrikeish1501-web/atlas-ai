import time

import chromadb
import ollama

from chunker import build_chunks
from config import CHROMA_DIR, COLLECTION_NAME, DOC_PREFIX, EMBED_MODEL
from pdf_reader import load_all_pdfs

BATCH_SIZE = 16  # how many chunks to embed per request


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Turn a list of chunk texts into a list of embedding vectors."""
    response = ollama.embed(model=EMBED_MODEL, input=[DOC_PREFIX + t for t in texts])
    return response["embeddings"]


def main() -> None:
    start_time = time.time()

    pages = load_all_pdfs()
    chunks = build_chunks(pages)
    print(f"Read {len(pages)} pages -> {len(chunks)} chunks")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Start fresh each time so re-running never creates duplicates.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # the collection did not exist yet

    collection = client.create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
    )

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        collection.add(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=embed_documents([c["text"] for c in batch]),
            metadatas=[
                {"source": c["source"], "page": c["page"], "chunk": c["chunk"]}
                for c in batch
            ],
        )
        print(f"  stored {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}")

    print(f"\nChromaDB now holds {collection.count()} chunks")

    sample = collection.get(ids=[chunks[0]["id"]], include=["metadatas", "documents"])
    print("\nSample record:")
    print("  id:      ", sample["ids"][0])
    print("  metadata:", sample["metadatas"][0])
    print("  text:    ", sample["documents"][0][:100], "...")

    print(f"\nDone in {time.time() - start_time:.1f} seconds")
    print(f"Database folder: {CHROMA_DIR}")


if __name__ == "__main__":
    main()