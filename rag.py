import re
import time

import ollama

from config import CHAT_MODEL
from search import get_collection, search

TOP_K = 5          # how many chunks to retrieve
MIN_SCORE = 0.60   # chunks scoring below this are treated as "not relevant"
NUM_CTX = 8192     # how much text the model can read at once (in tokens)
THINK = False      # False = faster direct answers, True = let Qwen3 reason first

NOT_FOUND = "I couldn't find this in the documents."

SYSTEM_PROMPT = f"""You are ATLAS AI, an engineering assistant for mechanical design, SolidWorks modelling and manufacturing.

Rules:
- Answer ONLY from the numbered context sources provided. Do not use outside knowledge.
- After each fact, cite its source label in square brackets, like [S1] or [S2][S3].
- If the sources do not contain the answer, reply exactly: {NOT_FOUND}
- Use simple language and short bullet points.
- Never invent numbers, values or page numbers that are not in the sources."""


def short_name(source: str) -> str:
    """Shorten a PDF file name for display."""
    return source.replace("Atlas_AI_", "").replace(".pdf", "")


def retrieve(question: str, collection=None):
    """Return (relevant_hits, best_score). Hits below MIN_SCORE are dropped."""
    all_hits = search(question, top_k=TOP_K, collection=collection)
    best_score = all_hits[0]["score"] if all_hits else 0.0
    relevant = [hit for hit in all_hits if hit["score"] >= MIN_SCORE]
    return relevant, best_score


def build_messages(question: str, hits: list[dict]) -> list[dict]:
    """Put the chunks and the question into the chat format the model expects."""
    blocks = []
    for number, hit in enumerate(hits, start=1):
        header = f"[S{number}] ({short_name(hit['source'])}, page {hit['page']})"
        blocks.append(f"{header}\n{hit['text']}")
    context = "\n\n".join(blocks)
    user_message = f"Context sources:\n\n{context}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def stream_answer(messages: list[dict]):
    """Yield the model's answer piece by piece as it is written."""
    stream = ollama.chat(
        model=CHAT_MODEL,
        messages=messages,
        stream=True,
        think=THINK,
        options={"temperature": 0.2, "num_ctx": NUM_CTX},
    )
    for part in stream:
        piece = part["message"]["content"]
        if piece:
            yield piece


def cited_sources(answer: str, hits: list[dict]) -> list[tuple[int, dict]]:
    """Find which [S#] labels the model used and map them back to file and page."""
    numbers = sorted({int(n) for n in re.findall(r"\bS(\d+)\b", answer)})
    cited = [(n, hits[n - 1]) for n in numbers if 1 <= n <= len(hits)]
    if not cited:  # the model forgot to cite, so show everything we gave it
        cited = list(enumerate(hits, start=1))
    return cited


def main() -> None:
    collection = get_collection()
    print(f"ATLAS AI ready. {collection.count()} chunks loaded. Type q to quit.")

    while True:
        question = input("\nYou> ").strip()
        if question.lower() in ("q", "quit", "exit"):
            break
        if not question:
            continue
        try:
            started = time.time()
            hits, best_score = retrieve(question, collection)
            if not hits:
                print(f"\nATLAS> {NOT_FOUND}")
                print(f"(best match scored {best_score}, below the {MIN_SCORE} cutoff)")
                continue

            print("\nATLAS> ", end="", flush=True)
            answer = ""
            for piece in stream_answer(build_messages(question, hits)):
                print(piece, end="", flush=True)
                answer += piece

            print("\n\nSources:")
            for number, hit in cited_sources(answer, hits):
                print(
                    f"  [S{number}] {short_name(hit['source'])}, "
                    f"page {hit['page']} (score {hit['score']})"
                )
            print(f"\n(answered in {time.time() - started:.1f} s)")
        except Exception as error:
            print(f"Error: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()