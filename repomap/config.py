from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib as _toml
except Exception:
    import tomli as _toml  # type: ignore

DEFAULTS: Dict[str, Any] = {
    "chunk_lines": 120,
    "exclude_dirs": [".git","node_modules",".venv","dist","build",".next",".cache",".pytest_cache",".mypy_cache",".idea",".vscode"],
    "text_ext": [
        ".py",".ts",".tsx",".js",".jsx",".mjs",".c",".cpp",".h",".hpp",".rs",".go",".java",".php",".rb",".cs",".swift",
        ".kt",".scala",".sql",".md",".yml",".yaml",".toml",".ini",".cfg",".txt",".html",".css",".scss"
    ],
    "ollama": {
        "enabled": True,
        "url": "http://127.0.0.1:11434",
        "model": "nomic-embed-text",
        "timeout": 10.0,
        "batch": 32,
        "weight_bm25": 0.5,
        "weight_emb": 0.5,
    },
}

def _read_toml(path: Path):
    try:
        with path.open("rb") as f:
            return _toml.load(f)
    except Exception:
        return {}

def find_config(repo_root: Path) -> Path | None:
    for p in [repo_root / ".repomap.toml", repo_root / ".repomap" / "config.toml", repo_root / "repomap.toml"]:
        if p.exists():
            return p
    return None

def load(repo_root: Path) -> Dict[str, Any]:
    cfg = DEFAULTS.copy()
    path = find_config(repo_root)
    if path:
        doc = _read_toml(path)
        if isinstance(doc, dict):
            if "chunk_lines" in doc: cfg["chunk_lines"] = int(doc["chunk_lines"])
            if "exclude_dirs" in doc and isinstance(doc["exclude_dirs"], list): cfg["exclude_dirs"] = list(doc["exclude_dirs"])
            if "text_ext" in doc and isinstance(doc["text_ext"], list): cfg["text_ext"] = list(doc["text_ext"])
            if "ollama" in doc and isinstance(doc["ollama"], dict):
                ol = cfg["ollama"].copy()
                ol.update(doc["ollama"])
                # normalize
                if "timeout" in ol: ol["timeout"] = float(ol["timeout"])
                if "batch" in ol: ol["batch"] = int(ol["batch"])
                if "weight_bm25" in ol: ol["weight_bm25"] = float(ol["weight_bm25"])
                if "weight_emb" in ol: ol["weight_emb"] = float(ol["weight_emb"])
                if "enabled" in ol: ol["enabled"] = bool(ol["enabled"])
                cfg["ollama"] = ol

    # env overrides
    e = os.environ
    if "REPOMAP_CHUNK_LINES" in e: cfg["chunk_lines"] = int(e["REPOMAP_CHUNK_LINES"])
    if "REPOMAP_OLLAMA_URL" in e: cfg["ollama"]["url"] = e["REPOMAP_OLLAMA_URL"]
    if "REPOMAP_EMBED_MODEL" in e: cfg["ollama"]["model"] = e["REPOMAP_EMBED_MODEL"]
    if "REPOMAP_OLLAMA_TIMEOUT" in e: cfg["ollama"]["timeout"] = float(e["REPOMAP_OLLAMA_TIMEOUT"])
    if "REPOMAP_EMBED_BATCH" in e: cfg["ollama"]["batch"] = int(e["REPOMAP_EMBED_BATCH"])
    if "REPOMAP_W_BM25" in e: cfg["ollama"]["weight_bm25"] = float(e["REPOMAP_W_BM25"])
    if "REPOMAP_W_EMB" in e: cfg["ollama"]["weight_emb"] = float(e["REPOMAP_W_EMB"])
    if "REPOMAP_OLLAMA_ENABLED" in e: cfg["ollama"]["enabled"] = e["REPOMAP_OLLAMA_ENABLED"].lower() not in {"0","false","no"}

    return cfg
