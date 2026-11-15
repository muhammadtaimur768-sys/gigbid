"""Repo ingestion through the official GitHub MCP server (github/github-mcp-server).

Connects with langchain-mcp-adapters' MultiServerMCPClient over streamable HTTP to the remote
endpoint in rag/config.yaml `github.mcp_url`, authenticated with a bearer token from $GITHUB_TOKEN
(a fine-grained, read-only "Contents: read" token is enough). For each `owner/name` in $GITHUB_REPOS
(or passed explicitly) it calls the `get_file_contents` tool for the README and up to
`max_code_files` code files at the repo root and in `src/`, and returns `Item(type="repo")`
objects that the normal chunkers and `Retriever.add_document` index.

When GITHUB_TOKEN is not set, `github_enabled()` is False and callers use the local loader
(`rag.ingest.loaders.load_repo`) on data/personas/<persona>/repos/ instead.

    GITHUB_TOKEN=... GITHUB_REPOS=me/rag-bot python -m rag.ingest.github_loader aiml
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from rag.config import load_config
from rag.types import Item


def github_enabled() -> bool:
    return bool(os.environ.get(load_config()["github"]["token_env"]))


def _text_of(result) -> str:
    parts = []
    for c in getattr(result, "content", []) or []:
        if getattr(c, "text", None):
            parts.append(c.text)
        res = getattr(c, "resource", None)
        if res is not None and getattr(res, "text", None):
            parts.append(res.text)
    return "\n".join(parts)


async def _fetch_repo(session, owner: str, name: str, gcfg: dict) -> dict:
    readme = _text_of(await session.call_tool("get_file_contents", {"owner": owner, "repo": name, "path": "README.md"}))
    files = []
    for folder in ("", "src/"):
        listing = _text_of(await session.call_tool("get_file_contents", {"owner": owner, "repo": name, "path": folder or "/"}))
        try:
            entries = json.loads(listing)
        except (json.JSONDecodeError, TypeError):
            continue
        for e in entries if isinstance(entries, list) else []:
            path = e.get("path") or e.get("name", "")
            if e.get("type") == "file" and any(path.endswith(x) for x in gcfg["code_ext"]):
                body = _text_of(await session.call_tool("get_file_contents", {"owner": owner, "repo": name, "path": path}))
                files.append({"path": path, "text": body})
            if len(files) >= gcfg["max_code_files"]:
                break
    return {"readme": readme, "files": files}


async def load_github_repos(persona: str, repos: list[str] | None = None) -> list[Item]:
    gcfg = load_config()["github"]
    token = os.environ.get(gcfg["token_env"])
    if not token:
        return []
    repos = repos or [r.strip() for r in os.environ.get(gcfg["repos_env"], "").split(",") if r.strip()]
    if not repos:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({"github": {"transport": "streamable_http", "url": gcfg["mcp_url"],
                                              "headers": {"Authorization": f"Bearer {token}"}}})
    items = []
    async with client.session("github") as session:
        for i, full in enumerate(repos, start=1):
            owner, name = full.split("/", 1)
            data = await _fetch_repo(session, owner, name, gcfg)
            items.append(Item(item_id=f"{persona}-gh-{i:02d}", persona=persona, type="repo", title=name,
                              project=name, text=data["readme"], source=f"https://github.com/{full}",
                              files=data["files"]))
    return items


def ingest_github(persona: str, repos: list[str] | None = None) -> list[dict]:
    """Fetch repos via the GitHub MCP server and index them incrementally. No-op without a token."""
    if not github_enabled():
        return []
    from rag.retriever import get_retriever

    r = get_retriever(persona)
    out = []
    for it in asyncio.run(load_github_repos(persona, repos)):
        out.append(r.add_document(it.item_id, "repo", it.text, title=it.title, project=it.project,
                                  source=it.source, files=it.files))
    return out


if __name__ == "__main__":
    persona = sys.argv[1] if len(sys.argv) > 1 else "aiml"
    if not github_enabled():
        print("GITHUB_TOKEN not set: GitHub MCP ingestion skipped (local repos/ loader is used).")
    else:
        print(json.dumps(ingest_github(persona, sys.argv[2:] or None), indent=2))
