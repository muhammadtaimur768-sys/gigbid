"""Render both graphs from code: `python -m agent.graphs.render` → docs/images/*.mmd (+ .png when offline rendering works)."""
from __future__ import annotations

import os
from pathlib import Path

from agent.marketplace_port import InMemoryMarketplace
from agent.settings import ROOT


def render(out_dir: Path | None = None) -> dict:
    os.environ.setdefault("TRACING_DISABLED", "1")
    from agent.graphs.bid_graph import build_bid_graph
    from agent.graphs.conversation_graph import build_conversation_graph

    out_dir = out_dir or ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    port = InMemoryMarketplace()
    written = {}
    for name, g in (("bid_graph", build_bid_graph(marketplace=port)),
                    ("conversation_graph", build_conversation_graph(marketplace=port))):
        dg = g.get_graph()
        mmd = dg.draw_mermaid()
        (out_dir / f"{name}.mmd").write_text(mmd)
        written[f"{name}.mmd"] = True
        try:  # offline PNG (pyppeteer/graphviz) if available; never calls a web service
            from langchain_core.runnables.graph import MermaidDrawMethod

            png = dg.draw_mermaid_png(draw_method=MermaidDrawMethod.PYPPETEER)
            (out_dir / f"{name}.png").write_bytes(png)
            written[f"{name}.png"] = True
        except Exception:
            try:
                (out_dir / f"{name}.png").write_bytes(dg.draw_png())
                written[f"{name}.png"] = True
            except Exception:
                written[f"{name}.png"] = False
    return written


if __name__ == "__main__":
    for k, v in render().items():
        print(f"{k}: {'written' if v else 'skipped (no offline renderer)'}")
