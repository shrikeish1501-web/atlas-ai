import gradio as gr

from rag import (
    MIN_SCORE,
    NOT_FOUND,
    build_messages,
    cited_sources,
    generate_answer,
    retrieve,
    short_name,
)
from search import get_collection

collection = get_collection()


def format_sources(answer: str, hits: list[dict]) -> str:
    """Build the Sources list shown under each answer."""
    items = []
    for number, hit in cited_sources(answer, hits):
        items.append(
            f"- [S{number}] {short_name(hit['source'])}, "
            f"page {hit['page']} (score {hit['score']})"
        )
    return "\n\n---\n**Sources**\n\n" + "\n".join(items)


def chat(message, history):
    """Answer one question. `history` is not used: every question stands alone."""
    question = message.strip() if isinstance(message, str) else ""
    if not question:
        yield "Please type a question."
        return

    try:
        yield "Searching the documents..."
        hits, best_score = retrieve(question, collection)
        if not hits:
            yield (
                f"{NOT_FOUND}\n\n"
                f"*(best match scored {best_score}, below the {MIN_SCORE} cutoff)*"
            )
            return

        yield "Thinking... (a local model can take 10 to 40 seconds)"
        answer = generate_answer(build_messages(question, hits))
        if not answer:
            yield "The model returned an empty answer. Please ask again."
            return
        if answer.startswith(NOT_FOUND):
            yield answer
            return

        yield answer + format_sources(answer, hits)
    except Exception as error:
        yield f"Error: {type(error).__name__}: {error}"


demo = gr.ChatInterface(
    fn=chat,
    title="ATLAS AI - Engineering Knowledge Assistant",
    description=(
        "Ask about SolidWorks part modelling and design for manufacturing. "
        "Answers come only from your PDFs and cite the file and page. "
        "Runs 100% locally."
    ),
    examples=[
        "Why are fillets commonly added near the end of modelling?",
        "What is the difference between a clearance hole and a tapped hole?",
        "Why do machined internal corners have a radius?",
        "Does STEP preserve the SOLIDWORKS feature tree?",
    ],
    cache_examples=False,
)

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), inbrowser=True)