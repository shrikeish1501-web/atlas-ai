from importlib.metadata import version

import ollama

print("=== Package versions ===")
for pkg in ["ollama", "chromadb", "pypdf", "gradio", "pywin32"]:
    print(f"{pkg}: {version(pkg)}")

print("\n=== Ollama models installed ===")
models = [m.model for m in ollama.list().models]
for name in models:
    print(" -", name)

print("\n=== Embedding test (nomic-embed-text) ===")
resp = ollama.embed(model="nomic-embed-text", input="A bracket with two mounting holes")
vector = resp["embeddings"][0]
print("Vector length:", len(vector))
print("First 3 numbers:", [round(x, 4) for x in vector[:3]])

print("\n=== ChromaDB test ===")
import chromadb

client = chromadb.Client()
collection = client.create_collection("test")
collection.add(ids=["1"], documents=["hello"], embeddings=[vector])
print("ChromaDB stored items:", collection.count())

print("\n=== SolidWorks COM library test ===")
import win32com.client  # noqa: F401

print("pywin32 import OK")

print("\nALL CHECKS PASSED")