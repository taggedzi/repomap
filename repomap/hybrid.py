from __future__ import annotations
import os
import json
import sqlite3
from typing import List, Optional, Tuple, Iterable, Dict
from pathlib import Path
import requests

def try_embed(texts: List[str], url: str, model: str, timeout: float) -> Optional[List[List[float]]]:
    api = f"{url.rstrip('/')}/api/embeddings"
    payload = {"model": model, "prompt": texts if len(texts) > 1 else texts[0]}
    try:
        r = requests.post(api, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if "embeddings" in data:
            return data["embeddings"]
        if "embedding" in data:
            return [data["embedding"]]
        return None
    except Exception:
        return None

def ensure_embeddings_table(con: sqlite3.Connection):
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS embeddings(
            chunk_id INTEGER PRIMARY KEY,
            model TEXT NOT NULL,
            vec TEXT NOT NULL,
            FOREIGN KEY(chunk_id) REFERENCES chunks(id)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model);")
    con.commit()

def load_cached_embeddings(con: sqlite3.Connection, model: str) -> Dict[int, List[float]]:
    cur = con.cursor()
    cur.execute("SELECT chunk_id, vec FROM embeddings WHERE model=?", (model,))
    out = {}
    for cid, vec_json in cur.fetchall():
        try:
            out[cid] = json.loads(vec_json)
        except Exception:
            continue
    return out

def cache_embeddings(con: sqlite3.Connection, model: str, pairs: Iterable[Tuple[int, List[float]]]):
    cur = con.cursor()
    rows = [(cid, model, json.dumps(vec)) for cid, vec in pairs]
    cur.executemany("INSERT OR REPLACE INTO embeddings(chunk_id, model, vec) VALUES(?,?,?)", rows)
    con.commit()

def hybrid_rank(dbfile: Path, question: str, bm25_scores, rows, cfg: dict | None):
    ol = (cfg or {}).get("ollama", {})
    url = ol.get("url", "http://127.0.0.1:11434")
    model = ol.get("model", "nomic-embed-text")
    timeout = float(ol.get("timeout", 10.0))
    batch = int(ol.get("batch", 32))
    w_bm25 = float(ol.get("weight_bm25", 0.5))
    w_emb = float(ol.get("weight_emb", 0.5))
    enabled = bool(ol.get("enabled", True))

    if not enabled:
        return None

    q_vecs = try_embed([question], url, model, timeout)
    if not q_vecs:
        return None
    q_vec = q_vecs[0]

    con = sqlite3.connect(dbfile)
    try:
        ensure_embeddings_table(con)
        cached = load_cached_embeddings(con, model)

        missing_ids, missing_texts = [], []
        for row in rows:
            chunk_id = row[0]
            if chunk_id not in cached:
                missing_ids.append(chunk_id)
                missing_texts.append(row[4])

        if missing_texts:
            new_vectors = {}
            for i in range(0, len(missing_texts), batch):
                batch_texts = missing_texts[i:i+batch]
                vecs = try_embed(batch_texts, url, model, timeout)
                if not vecs or len(vecs) != len(batch_texts):
                    return None
                for k, vec in enumerate(vecs):
                    new_vectors[missing_ids[i+k]] = vec
            cache_embeddings(con, model, new_vectors.items())
            cached.update(new_vectors)

        # cosine(q, vec)
        import math
        qn = math.sqrt(sum(x*x for x in q_vec)) or 1e-9
        finals = []
        for i, row in enumerate(rows):
            vec = cached.get(row[0])
            if not vec:
                return None
            vn = math.sqrt(sum(y*y for y in vec)) or 1e-9
            cos = sum(x*y for x, y in zip(q_vec, vec)) / (qn * vn)
            finals.append((i, (w_bm25 * bm25_scores[i]) + (w_emb * cos)))
        return finals
    finally:
        con.close()
