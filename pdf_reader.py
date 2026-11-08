from pathlib import Path

from pypdf import PdfReader

DATA_DIR = Path(__file__).parent / "data"


def load_pdf_pages(pdf_path: Path) -> list[dict]:
    """Read one PDF and return a list of pages: {"source", "page", "text"}."""
    reader = PdfReader(str(pdf_path))
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append({"source": pdf_path.name, "page": page_number, "text": text})
    return pages


def load_all_pdfs(data_dir: Path = DATA_DIR) -> list[dict]:
    """Read every PDF in the data folder and return all pages together."""
    all_pages = []
    for pdf_path in sorted(data_dir.glob("*.pdf")):
        all_pages.extend(load_pdf_pages(pdf_path))
    return all_pages


if __name__ == "__main__":
    pdf_files = sorted(DATA_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {DATA_DIR}. Copy your PDFs into the data folder first.")
        raise SystemExit(1)

    pages = load_all_pdfs()
    for pdf_path in pdf_files:
        file_pages = [p for p in pages if p["source"] == pdf_path.name]
        print(f"\n=== {pdf_path.name} ===")
        print(f"Pages read: {len(file_pages)}")
        for p in file_pages:
            preview = " ".join(p["text"].split())[:70]
            print(f"  page {p['page']:>2} | {len(p['text']):>5} chars | {preview}")
            if not p["text"]:
                print("    WARNING: no text on this page (scanned image?)")
    print(f"\nTotal pages: {len(pages)}")