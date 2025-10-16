# repomap

Local repo context with **BM25**, optional **Ollama embeddings hybrid**, **per-repo TOML config**, and an optional **MCP** wrapper.

## Per-repo config

Create `.repomap.toml` in your repo:

```toml
chunk_lines = 140
exclude_dirs = [".git","node_modules",".venv","dist","build"]
text_ext = [".py",".ts",".tsx",".js",".jsx",".md",".yaml",".toml",".sql",".php",".html",".css",".scss"]

[ollama]
enabled = true
url = "http://127.0.0.1:11434"
model = "nomic-embed-text"
timeout = 10.0
batch = 32
weight_bm25 = 0.5
weight_emb  = 0.5
```

**Precedence:** env vars override TOML; TOML overrides built-in defaults.

## CLI

```powershell
python -m venv .repomap-venv
.\.repomap-venv\Scripts\activate
pip install -e .

repomap-index .
repomap-query . "where is auth middleware created and how is it wired?" 12
```

Outputs `.continue/context/CONTEXT_SNIPPETS.md` for @Files in Continue.

## MCP

```powershell
repomap-mcp
```

`examples/repomap.yaml` shows a Continue config. Tools: `refresh_index`, `search`, `open_file`, `list_files`, `help`, `capabilities`.
