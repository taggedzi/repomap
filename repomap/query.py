import sys
import json
import re
import sqlite3
import heapq
from pathlib import Path
from rank_bm25 import BM25Okapi

from .indexer import db_path
from .hybrid import hybrid_rank
from . import config as repoconfig

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")

def tokenize(s: str):
    return TOKEN_RE.findall(s.lower())

def fetch_chunks(dbfile: Path):
    con = sqlite3.connect(dbfile)
    cur = con.cursor()
    cur.execute(
        """SELECT c.id, f.path, c.start_line, c.end_line, c.text
           FROM chunks c JOIN files f ON f.id=c.file_id"""
    )
    rows = cur.fetchall()
    con.close()
    return rows

def search(root: Path, question: str, k: int = 12):
    cfg = repoconfig.load(root)
    dbfile = db_path(root)
    rows = fetch_chunks(dbfile)
    if not rows:
        return []

    docs = [tokenize(r[4]) for r in rows]
    bm25 = BM25Okapi(docs)
    q_tokens = tokenize(question)
    bm25_scores = list(bm25.get_scores(q_tokens))

    finals = hybrid_rank(dbfile, question, bm25_scores, rows, cfg)

    if finals is None:
        top = heapq.nlargest(k, enumerate(bm25_scores), key=lambda x: x[1])
    else:
        top = heapq.nlargest(k, finals, key=lambda x: x[1])

    top_scores = dict(top)
    ranked_idxs = [i for i, _ in top]

    results = []
    for i in ranked_idxs:
        (chunk_id, path, a, b, text) = rows[i]
        score = float(top_scores.get(i, 0.0))
        results.append({
            "path": path,
            "start": int(a),
            "end": int(b),
            "score": score,
            "snippet": "\n".join(text.splitlines()[:300]),
        })
    return results

def write_markdown(root: Path, question: str, results):
    out = root / ".continue" / "context" / "CONTEXT_SNIPPETS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# CONTEXT for: {question}\n\n")
        for r in results:
            f.write(f"## {r['path']}  (lines {r['start']}-{r['end']})  — score {r['score']:.3f}\n\n")
            f.write("```text\n")
            f.write(r["snippet"])
            f.write("\n```\n\n")
    return out

def cli():
    if len(sys.argv) < 3:
        print("Usage: repomap-query <root> <question> [k]")
        sys.exit(1)
    root = Path(sys.argv[1]).resolve()
    question = sys.argv[2]
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    results = search(root, question, k)
    out = write_markdown(root, question, results)
    print(json.dumps({"wrote": str(out), "results": len(results)}))
