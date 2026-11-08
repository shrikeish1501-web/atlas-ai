from pdf_reader import load_all_pdfs

CHUNK_SIZE = 800     # maximum characters per chunk
CHUNK_OVERLAP = 150  # characters shared between neighbouring chunks


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Cut one page of text into overlapping chunks, breaking at sentence ends or spaces."""
    text = " ".join(text.split())  # turn newlines and repeated spaces into single spaces
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer to cut right after a sentence end; otherwise cut at a space.
            cut = text.rfind(". ", start + size // 2, end)
            if cut != -1:
                end = cut + 1
            else:
                cut = text.rfind(" ", start + size // 2, end)
                if cut != -1:
                    end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        # Step back by `overlap` characters, then move forward to the next word start.
        start = max(end - overlap, start + 1)
        next_space = text.find(" ", start, end)
        if next_space != -1:
            start = next_space + 1
    return chunks


def build_chunks(pages: list[dict]) -> list[dict]:
    """Turn page records into chunk records that remember their file and page."""
    chunks = []
    for page in pages:
        for number, piece in enumerate(split_text(page["text"]), start=1):
            chunks.append(
                {
                    "id": f"{page['source']}::p{page['page']}::c{number}",
                    "source": page["source"],
                    "page": page["page"],
                    "chunk": number,
                    "text": piece,
                }
            )
    return chunks


if __name__ == "__main__":
    pages = load_all_pdfs()
    chunks = build_chunks(pages)

    print(f"Pages: {len(pages)}")
    print(f"Chunks: {len(chunks)}")
    for source in sorted({c["source"] for c in chunks}):
        count = sum(1 for c in chunks if c["source"] == source)
        print(f"  {source}: {count} chunks")

    lengths = [len(c["text"]) for c in chunks]
    print(
        f"Chunk length (characters): min={min(lengths)}, "
        f"average={sum(lengths) // len(lengths)}, max={max(lengths)}"
    )

    print("\n--- Sample: first 2 chunks of page 2 of the SolidWorks guide ---")
    sample = [
        c for c in chunks
        if c["source"].startswith("Atlas_AI_SolidWorks") and c["page"] == 2
    ][:2]
    for c in sample:
        print(f"\n[{c['id']}] ({len(c['text'])} characters)")
        print(c["text"])