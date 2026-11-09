from rag import MIN_SCORE, TOP_K
from search import get_collection, search

SW = "Atlas_AI_SolidWorks_2025_Part_Modeling_Guide.pdf"
DFM = "Atlas_AI_Design_for_Manufacturing_Handbook.pdf"
LABEL = {SW: "SW", DFM: "DFM"}

# (question, pages that contain the answer)
# A test passes if ANY of these pages appears in the top results.
IN_DOMAIN = [
    ("In what order should I add features when modelling a part?", [(SW, 2)]),
    ("What does an over-defined sketch mean and how do I fix it?", [(SW, 3)]),
    ("When should I use a revolve instead of an extrude?", [(SW, 3), (SW, 4)]),
    ("Why should edge rounding be left to the end of the feature tree?", [(SW, 4)]),
    ("My shell feature failed. What can I try?", [(SW, 5), (SW, 9)]),
    ("What is the difference between cosmetic threads and full helical threads?", [(SW, 6)]),
    ("Does exporting to STEP keep the feature history?", [(SW, 8)]),
    ("Which file format should I export for 3D printing?", [(SW, 8), (DFM, 4)]),
    ("A rebuild error appeared after I edited a sketch. What should I check first?", [(SW, 9)]),
    ("Why are deep narrow pockets a problem in CNC milling?", [(DFM, 2), (DFM, 3)]),
    ("What must be confirmed with the supplier before releasing a sheet metal flat pattern?", [(DFM, 3), (DFM, 4), (DFM, 8)]),
    ("Why does build orientation matter in 3D printing?", [(DFM, 4)]),
    ("How is draft used in injection moulded parts?", [(DFM, 5)]),
    ("What is the difference between a clearance fit and an interference fit?", [(DFM, 7)]),
    ("Why shouldn't every dimension have a very tight tolerance?", [(DFM, 6), (DFM, 7)]),
    ("How should a tapped hole be called out on a drawing?", [(SW, 6), (SW, 7), (DFM, 6)]),
    ("What should be specified on a drawing for a welded part?", [(DFM, 6)]),
    ("Should I machine this bracket or make it from sheet metal?", [(DFM, 2), (DFM, 8)]),
    ("Which tool checks internal diameters during inspection?", [(DFM, 7)]),
    ("How do I keep four mounting holes symmetric when the plate width changes?", [(SW, 7)]),
]

# Questions that have nothing to do with the PDFs: the cutoff should block them.
OFF_TOPIC = [
    "What is the best pizza topping?",
    "Who won the last cricket world cup?",
    "How do I reset my Wi-Fi router?",
]

# In the topic area, but the PDFs do not contain the answer.
NOT_IN_DOCS = [
    "What is the yield strength of 6061 aluminium?",
    "What is the price of a SolidWorks licence?",
]


def first_hit_rank(hits, expected):
    """Return the rank (1 = best) of the first correct page, or None."""
    for rank, hit in enumerate(hits, start=1):
        if (hit["source"], hit["page"]) in expected:
            return rank
    return None


def describe(pages):
    return ", ".join(f"{LABEL[source]} p{page}" for source, page in pages)


def main() -> None:
    collection = get_collection()

    print(f"=== In-domain questions (checking the top {TOP_K} results) ===")
    ranks = []
    best_scores = []
    for number, (question, expected) in enumerate(IN_DOMAIN, start=1):
        hits = search(question, top_k=TOP_K, collection=collection)
        rank = first_hit_rank(hits, expected)
        ranks.append(rank)
        best_scores.append(hits[0]["score"])
        status = f"PASS #{rank}" if rank else "MISS   "
        print(f"{number:>2}. {status}  best={hits[0]['score']:.3f}  {question}")
        if rank is None:
            got = [(hit["source"], hit["page"]) for hit in hits]
            print(f"      wanted: {describe(expected)}")
            print(f"      got:    {describe(got)}")

    total = len(IN_DOMAIN)
    print("\n=== Summary ===")
    for k in (1, 3, TOP_K):
        found = sum(1 for rank in ranks if rank is not None and rank <= k)
        print(f"Hit@{k}: {found}/{total} ({100 * found // total}%)")

    print("\n=== Off-topic questions (should be BLOCKED) ===")
    off_scores = []
    for question in OFF_TOPIC:
        best = search(question, top_k=1, collection=collection)[0]["score"]
        off_scores.append(best)
        status = "BLOCKED    " if best < MIN_SCORE else "NOT BLOCKED"
        print(f"    {status} best={best:.3f}  {question}")

    print("\n=== In the topic area but NOT in the PDFs ===")
    for question in NOT_IN_DOCS:
        best = search(question, top_k=1, collection=collection)[0]["score"]
        status = "BLOCKED    " if best < MIN_SCORE else "NOT BLOCKED"
        print(f"    {status} best={best:.3f}  {question}")

    print("\n=== Cutoff check ===")
    print(f"Lowest best-score of an in-domain question: {min(best_scores):.3f}")
    print(f"Highest best-score of an off-topic question: {max(off_scores):.3f}")
    print(f"Current cutoff (MIN_SCORE): {MIN_SCORE}")


if __name__ == "__main__":
    main()