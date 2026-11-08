import re
import time

import ollama

from config import CHAT_MODEL
from search import get_collection, search

TOP_K = 5          # how many chunks to retrieve
MIN_SCORE = 0.60   # chunks scoring below this are treated as "not relevant"
NUM_CTX = 8192     # how much text the model can read at once (in tokens)
THINK = True       # keeps the model's reasoning separate from its final answer

NOT_FOUND = "I couldn't find this in the documents."

SYSTEM_PROMPT = f"""You are ATLAS AI, an engineering assistant for mechanical design, SolidWorks modelling and manufacturing.

Rules:
- Answer ONLY from the numbered context sources provided. Do not use outside knowledge.
- Give 2 to 5 short bullet points in simple language. Include every relevant point from the sources.
- After each fact, cite its source label in square brackets, like [S1] or [S2][S3].
- If the sources are about the topic but do not contain the specific answer (for example a number), say what the sources DO say and state clearly that they do not give that specific value.
- If the sources are unrelated to the question, reply exactly: {NOT_FOUND}
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


def clean_answer(text: str) -> str:
    """Remove any leftover reasoning text and keep only the final answer."""
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.replace("<think>", "").strip()


def generate_answer(messages: list[dict]) -> str:
    """Ask Qwen3 for the answer and return it as clean text."""
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=messages,
        think=THINK,
        options={
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "num_ctx": NUM_CTX,
        },
    )
    return clean_answer(response["message"]["content"])


def cited_sources(answer: str, hits: list[dict]) -> list[tuple[int, dict]]:
    """Find which [S#] labels the answer used and map them back to file and page."""
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

            print("\nATLAS is thinking...")
            answer = generate_answer(build_messages(question, hits))
            if not answer:
                print("\nATLAS> (the model returned an empty answer - please ask again)")
                continue
            print(f"\nATLAS> {answer}")

            if not answer.startswith(NOT_FOUND):
                print("\nSources:")
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