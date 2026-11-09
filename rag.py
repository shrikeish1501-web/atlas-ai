"""ATLAS AI - retrieval-augmented answers over engineering PDFs.

Pipeline: question -> search ChromaDB -> keep the relevant chunks -> ask the
local Qwen3 model to answer ONLY from those chunks -> print answer + sources.

Run in the terminal:  python rag.py
The Gradio web page (app.py) imports the functions defined here.
"""

import re
import time

import ollama

from config import CHAT_MODEL
from search import get_collection, search

# ----- Settings (tuned in Step 9 with eval_retrieval.py) -----
TOP_K = 8          # how many chunks to retrieve
MIN_SCORE = 0.63   # chunks scoring below this count as "not relevant"
NUM_CTX = 8192     # how much text the model can read at once (in tokens)

NOT_FOUND = "I couldn't find this in the documents."

SYSTEM_PROMPT = f"""You are ATLAS AI, an engineering assistant for mechanical design, SolidWorks modelling and manufacturing.

Rules:
- Answer ONLY from the numbered context sources provided. Do not use outside knowledge.
- Give short bullet points in simple language (usually 2 to 8). Include every relevant point from the sources.
- After each fact, cite its source label in square brackets, like [S1] or [S2][S3].
- Use only the sources that directly answer the question. Ignore sources about other topics, and do not add conclusions that the sources do not state.
- If the sources discuss the topic of the question but do not give the exact detail asked for (for example a specific number or value), do NOT refuse. Say what the sources DO say about the topic, then end with one bullet stating that the documents do not give that specific detail.
- Add that "documents do not give" bullet ONLY when the question asks for a specific detail that is missing. If the sources fully answer the question, add no disclaimer.
- Reply with exactly "{NOT_FOUND}" ONLY if none of the sources mention the topic of the question at all.
- Never invent numbers, values or page numbers that are not in the sources.

Example of a partial answer (follow the pattern, do not copy the content):
Question: What wall thickness should I use for a moulded part?
Answer:
- The sources say wall thickness should be reasonably uniform to avoid sink marks and warpage [S1].
- The documents do not give a specific wall thickness value."""


def model_settings(model_name: str):
    """Return (think, sampling options) that suit the chosen model.

    - "instruct" builds answer directly, so the `think` option must not be sent.
    - Other Qwen3 builds reason first; think=True keeps that reasoning out of the answer.
    """
    if "instruct" in model_name.lower():
        return None, {"temperature": 0.3, "top_p": 0.8, "top_k": 20}
    return True, {"temperature": 0.6, "top_p": 0.95, "top_k": 20}


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
    """Keep only the final answer: drop reasoning text and filler disclaimers."""
    if "</think>" in text:
        text = text.split("</think>")[-1]
    text = text.replace("<think>", "").strip()

    # Small models sometimes add a plain closing sentence such as
    # "The documents do not give that specific detail." even after a full answer.
    # A real "missing detail" statement is written as a bullet, so we only
    # remove closing lines that are NOT bullets.
    lines = text.splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
        elif not last.startswith("-") and last.lower().startswith("the documents do not give"):
            lines.pop()
        else:
            break
    return "\n".join(lines).strip()


def generate_answer(messages: list[dict]) -> str:
    """Ask the chat model for the answer and return it as clean text."""
    think, sampling = model_settings(CHAT_MODEL)
    extra = {} if think is None else {"think": think}
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=messages,
        options={**sampling, "num_ctx": NUM_CTX},
        **extra,
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
    print(
        f"ATLAS AI ready. {collection.count()} chunks loaded. "
        f"Model: {CHAT_MODEL}. Type q to quit."
    )

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