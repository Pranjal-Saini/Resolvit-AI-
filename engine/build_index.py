"""Build the FAISS index over engine/policy_docs/*.md. Run: python -m engine.build_index"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
DOCS, INDEX = ROOT / "policy_docs", ROOT / "index"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SIZE, OVERLAP = 500, 80


def chunk_docs() -> list[dict]:
    chunks = []
    for path in sorted(DOCS.glob("*.md")):
        # Split on "## " headings; text before the first one (title, sources) is not policy.
        for part in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)[1:]:
            section, _, body = part.partition("\n")
            body = " ".join(body.split())
            for start in range(0, max(len(body) - OVERLAP, 1), SIZE - OVERLAP):
                chunks.append({"text": body[start:start + SIZE], "source": path.name, "section": section.strip()})
    return chunks


def main():
    import faiss
    from sentence_transformers import SentenceTransformer

    chunks = chunk_docs()
    model = SentenceTransformer(MODEL)
    # Embed "section: text" so the heading helps retrieval.
    vecs = model.encode([f"{c['section']}: {c['text']}" for c in chunks], normalize_embeddings=True)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    INDEX.mkdir(exist_ok=True)
    faiss.write_index(index, str(INDEX / "faiss.index"))
    (INDEX / "chunks.json").write_text(json.dumps(chunks, indent=1), encoding="utf-8")
    print(f"indexed {len(chunks)} chunks from {len(list(DOCS.glob('*.md')))} docs -> {INDEX}")


if __name__ == "__main__":
    main()
