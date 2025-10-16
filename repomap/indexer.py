import os
import sqlite3
import sys
import json
import time
from pathlib import Path
from . import config as repoconfig

def is_text_file(p: Path, text_ext) -> bool:
    if p.suffix.lower() in text_ext:
        return True
    try:
        with open(p, "rb") as f:
            b = f.read(2048)
        b.decode("utf-8")
        return True
    except Exception:
        return False

def walk_files(root: Path, exclude_dirs, text_ext):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.is_file() and is_text_file(p, text_ext):
                yield p

def chunks(lines, n):
    buf = []
    start = 0
    for i, line in enumerate(lines, 1):
        buf.append(line)
        if i % n == 0:
            yield start, i, "".join(buf)
            buf = []
            start = i
    if buf:
        yield start, start + len(buf), "".join(buf)

def db_path(root: Path) -> Path:
    db = root / ".continue" / "context" / "repo_index.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    return db

def init_db(dbfile: Path):
    con = sqlite3.connect(dbfile)
    cur = con.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS files(
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            mtime REAL,
            size INTEGER
        );
        CREATE TABLE IF NOT EXISTS chunks(
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            chunk_idx INTEGER,
            start_line INTEGER,
            end_line INTEGER,
            text TEXT,
            FOREIGN KEY(file_id) REFERENCES files(id)
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);
        """
    )
    con.commit()
    con.close()

def index_repo(root: Path) -> dict:
    cfg = repoconfig.load(root)
    chunk_lines = int(cfg["chunk_lines"])
    exclude_dirs = set(cfg["exclude_dirs"])
    text_ext = set(s.lower() for s in cfg["text_ext"])

    dbfile = db_path(root)
    init_db(dbfile)
    con = sqlite3.connect(dbfile)
    cur = con.cursor()
    added = updated = 0

    for p in walk_files(root, exclude_dirs, text_ext):
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        rel = str(p.relative_to(root))
        cur.execute("SELECT id, mtime, size FROM files WHERE path=?", (rel,))
        row = cur.fetchone()
        if row and abs(row[1] - st.st_mtime) < 1 and row[2] == st.st_size:
            continue
        if row:
            file_id = row[0]
            cur.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
            cur.execute("UPDATE files SET mtime=?, size=? WHERE id=?", (st.st_mtime, st.st_size, file_id))
            updated += 1
        else:
            cur.execute("INSERT INTO files(path, mtime, size) VALUES(?,?,?)", (rel, st.st_mtime, st.st_size))
            file_id = cur.lastrowid
            added += 1

        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            continue

        for idx, (a, b, txt) in enumerate(chunks(lines, chunk_lines)):
            cur.execute(
                "INSERT INTO chunks(file_id, chunk_idx, start_line, end_line, text) VALUES(?,?,?,?,?)",
                (file_id, idx, a + 1, b, txt),
            )

    con.commit()
    con.close()
    return {"added": added, "updated": updated, "db": str(dbfile)}

def cli():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    t0 = time.time()
    result = index_repo(root)
    result["elapsed_s"] = round(time.time() - t0, 2)
    print(json.dumps(result))
