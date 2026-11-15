"""Policy retrieval: get_policy(query) -> cited rules from the FAISS index."""
import json
import sys
from functools import lru_cache

from shared.contracts import PolicyResult
from engine.build_index import INDEX, MODEL

THRESHOLD = 0.35  # below this the top hit is "low confidence": no money actions, escalate


@lru_cache(maxsize=1)
def _load():
    import faiss
    from sentence_transformers import SentenceTransformer

    if not (INDEX / "faiss.index").exists():
        from engine import build_index
        build_index.main()
    chunks = json.loads((INDEX / "chunks.json").read_text(encoding="utf-8"))
    return SentenceTransformer(MODEL), faiss.read_index(str(INDEX / "faiss.index")), chunks


def get_policy(query: str, k: int = 3) -> list[PolicyResult]:
    model, index, chunks = _load()
    scores, ids = index.search(model.encode([query], normalize_embeddings=True), k)
    return [
        PolicyResult(rule_text=chunks[i]["text"], source=chunks[i]["source"], section=chunks[i]["section"],
                     score=round(float(s), 3), low_confidence=float(s) < THRESHOLD)
        for s, i in zip(scores[0], ids[0]) if i != -1
    ]


if __name__ == "__main__":
    for r in get_policy(" ".join(sys.argv[1:]) or "money debited but transaction failed"):
        print(f"{r.score:.3f} {'LOW ' if r.low_confidence else ''}{r.source}#{r.section}")
