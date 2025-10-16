from pathlib import Path
try:
    from mcp.server import Server
except Exception as e:
    raise RuntimeError("Install the 'mcp' package to run this server.") from e

from .indexer import index_repo
from .query import search as search_chunks
from . import config as repoconfig

server = Server("repomap")

@server.tool()
async def refresh_index(root: str = "."):
    """Rebuild/update the local index for the repo at `root`."""
    root_path = Path(root).resolve()
    result = index_repo(root_path)
    return result

@server.tool()
async def search(question: str, k: int = 12, root: str = "."):
    """Return top-K relevant snippets. Uses hybrid if available; else BM25."""
    root_path = Path(root).resolve()
    results = search_chunks(root_path, question, k)
    return {"question": question, "k": int(k), "results": results}

@server.tool()
async def open_file(path: str, start: int = 1, end: int = 300):
    """Open a file and return a line-bounded slice (inclusive)."""
    p = Path(path)
    if not p.exists():
        return {"error": f"not found: {path}"}
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        start = max(1, int(start))
        end = min(len(lines), int(end))
        snippet = "".join(lines[start - 1 : end])
        return {"path": str(p), "start": start, "end": end, "text": snippet}
    except Exception as e:
        return {"error": str(e)}

@server.tool()
async def list_files(glob: str = "**/*"):
    """List files under CWD matching a glob (text-likely only)."""
    root = Path(".")
    paths = [str(p) for p in root.glob(glob) if p.is_file()]
    return {"count": len(paths), "files": paths[:5000]}

@server.tool()
async def capabilities(root: str = "."):
    """Return effective configuration for the repo at `root`."""
    cfg = repoconfig.load(Path(root).resolve())
    return cfg

@server.tool()
async def help():
    """Usage guidance and config locations."""
    return {
        "name": "repomap",
        "version": "0.3.0",
        "config_files": [".repomap.toml", ".repomap/config.toml", "repomap.toml"],
        "quickstart": [
            "1) Create .repomap.toml in repo root (see examples).",
            "2) Call refresh_index(root='.')",
            "3) Call search(question='auth wiring?', k=12, root='.')",
        ],
        "notes": [
            "Hybrid uses Ollama if enabled; otherwise BM25-only.",
            "Env vars override TOML values at runtime.",
            "DB path: .continue/context/repo_index.sqlite",
        ],
    }

def main():
    server.run_stdio()

if __name__ == "__main__":
    main()
