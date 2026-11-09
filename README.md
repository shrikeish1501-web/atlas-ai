\# ATLAS AI



A free, fully local AI assistant that answers questions about mechanical-design PDFs and \*\*cites the file and page\*\* for every answer. Built as a personal engineering project by a B.Tech Smart Manufacturing student. Day 2 adds text-to-CAD for SolidWorks.



\## Features



\- Runs 100% locally with Ollama: no API keys, no cloud, no cost

\- Page-level citations: every fact is tagged `\[S#]` and mapped back to file and page

\- Relevance cutoff: off-topic questions are refused instead of guessed

\- Honest partial answers: says when the documents do not contain a specific value

\- Gradio chat page and a terminal chat

\- Measured retrieval quality on a 20-question test set



\## How it works



```

PDFs -> pypdf (text per page)

&#x20;    -> chunker (800 chars, 150 overlap, keeps file + page)

&#x20;    -> nomic-embed-text embeddings -> ChromaDB (cosine)



Question -> embed -> top-8 chunks -> score cutoff (0.63)

&#x20;        -> Qwen3-4B-Instruct answers ONLY from those chunks

&#x20;        -> answer + cited sources

```



\## Tech stack



Python 3.11, Ollama (`qwen3:4b-instruct-2507-q4\_K\_M`, `nomic-embed-text`), ChromaDB, pypdf, Gradio 6.



\## Results



Tested on 20 rephrased questions (not copied from the PDFs):



| Metric | Result |

|---|---|

| Correct page is the top result (Hit@1) | 85% (17/20) |

| Correct page in top 3 (Hit@3) | 100% (20/20) |

| Correct page in top 5 (Hit@5) | 100% (20/20) |

| Off-topic / not-in-PDF questions blocked | 5 of 5 |

| Answer time (RTX 5050, 8 GB) | about 2-8 seconds |



Switching from a reasoning model (22-45 s per answer) to the non-thinking Instruct model cut answer time by roughly 5-10x.



\## Setup (Windows)



```powershell

ollama pull qwen3:4b-instruct-2507-q4\_K\_M

ollama pull nomic-embed-text

py -3.11 -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

pip install -r requirements.txt

python ingest.py     # builds the ChromaDB index from the PDFs in data/

python app.py        # opens the chat page at http://127.0.0.1:7860

```



Other commands: `python rag.py` (terminal chat), `python eval\_retrieval.py` (retrieval test).



\## Project structure



| File | Purpose |

|---|---|

| `pdf\_reader.py` | Reads PDFs page by page |

| `chunker.py` | Splits pages into overlapping chunks, keeping file and page |

| `ingest.py` | Embeds chunks and stores them in ChromaDB |

| `search.py` | Semantic search |

| `rag.py` | Retrieval, prompt, local LLM answer, citations |

| `app.py` | Gradio chat page |

| `eval\_retrieval.py` | Retrieval test set (Hit@k and cutoff check) |

| `config.py` | Models and paths |

| `data/` | Source PDFs (original training documents written for this project) |



\## Known limitations



\- Each question is answered on its own (no chat memory yet).

\- Long step-by-step answers can miss steps that sit in a neighbouring chunk. Idea: pull in neighbouring chunks.

\- Text PDFs only. Scanned PDFs would need OCR.

\- The 0.63 cutoff was tuned on 20 questions; very short or vague questions may need a different value.

\- A small local model can occasionally add filler or over-generalise. Every answer cites its sources so it can be checked.



\## Roadmap



\- Day 2: text-to-CAD for SolidWorks (LLM writes JSON, Python builds the part through the COM API)

\- Excel/CSV question answering with Pandas

\- Chat memory and neighbouring-chunk expansion

