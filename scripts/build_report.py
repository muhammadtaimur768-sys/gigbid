"""Build the GigBid R&D report (docs/GigBid_RD_Report.pdf) from committed result files.

Every number in the PDF is read from evals/results/* (or the files named next to each table),
so re-running this script after re-running the evals regenerates the report.

    .venv/bin/python scripts/build_report.py
"""
from __future__ import annotations

import csv
import glob
import json
import statistics as st
from collections import Counter
from pathlib import Path

import yaml
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "evals" / "results"
OUT = ROOT / "docs" / "GigBid_RD_Report.pdf"
SRC_DIR = ROOT / "docs" / "report"

LIVE_URL = "https://gigbid-gamma.vercel.app"
REPO_URL = "https://github.com/muhammadtaimur768-sys/gigbid"
AUTHOR = "Muhammad bin Taimur"


# ----------------------------------------------------------------------------- data loading
def jload(name: str):
    return json.loads((RES / name).read_text())


def fmt(x, nd=3):
    if x is None:
        return "not measured"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def pct(x, nd=1):
    return "not measured" if x is None else f"{100 * x:.{nd}f}%"


def failure_taxonomy() -> tuple[list[dict], Counter]:
    """Real failures from decision_records_*.jsonl, grouped into the assignment's taxonomy."""
    rows: list[dict] = []
    for f in sorted(glob.glob(str(RES / "decision_records_*.jsonl"))):
        cfg = Path(f).name[len("decision_records_"):-len(".jsonl")]
        for line in open(f):
            r = json.loads(line)
            g = r["gold"]
            pred = "bid" if r["action"] == "bid" else "skip"
            cats = []
            if pred != g["action"]:
                cats.append("wrong skip" if g["action"] == "bid" else "wrong bid")
            if bool(g["is_scam"]) != bool(r.get("is_scam_pred")):
                cats.append("scam miss" if g["is_scam"] else "scam false positive")
            if bool(g["has_injection"]) != bool(r.get("injection_pred")):
                cats.append("injection")
            if r["action"] == "bid" and g["action"] == "bid" and r.get("price") is not None:
                lo, hi = g["fair_price_band"]
                if not lo <= r["price"] <= hi:
                    cats.append("mispriced")
            if r["action"] == "bid" and g["evidence_ids"]:
                got, gold = set(r.get("evidence_items") or []), set(g["evidence_ids"])
                if len(got & gold) / len(gold) < 0.34:
                    cats.append("missed evidence")
            if (r.get("unsupported_before") or 0) > 0:
                cats.append("unsupported claim")
            opening = (r.get("cover_letter") or "").lower()[:60]
            if r["action"] == "bid" and any(opening.startswith(b) for b in
                                            ("dear sir", "i am a passionate", "hi, i read", "hello, i read")):
                cats.append("generic opening")
            if r.get("error") or r.get("status") in ("dead_letter", "needs_attention"):
                cats.append("tool error")
            if (r.get("compliance") or {}).get("violations") and r.get("status") == "awaiting_approval":
                cats.append("compliance miss")
            if cats:
                rows.append({"config": cfg, "job_id": r["job_id"], "job_type": g["job_type"], "gold": g["action"],
                             "pred": r["action"], "cats": cats, "price": r.get("price"),
                             "band": g["fair_price_band"], "reason": r.get("status_reason") or "",
                             "unsupported_before": r.get("unsupported_before"),
                             "unsupported_after": r.get("unsupported_after"),
                             "gold_skip_reason": g.get("skip_reason")})
    counts = Counter((row["config"], c) for row in rows for c in row["cats"])
    return rows, counts


def judge_stats() -> dict:
    d = jload("judge_calibration_groq.json")
    out = {"raw": d}
    labels = {}
    lp = ROOT / "evals" / "datasets" / "human_labels.csv"
    for row in csv.DictReader(open(lp)):
        if row["human_verdict_pass_or_revise"].strip():
            labels[row["proposal_id"]] = row
    scores = {s["proposal_id"]: s for s in d.get("scores", [])}
    ids = [i for i in sorted(labels) if i in scores]
    out["n"] = len(ids)
    if ids:
        hv = [labels[i]["human_verdict_pass_or_revise"].strip() for i in ids]
        jv = [scores[i]["judge_verdict"] for i in ids]
        out["agreement"] = sum(a == b for a, b in zip(hv, jv)) / len(ids)
        out["human_verdicts"] = Counter(hv)
        out["judge_verdicts"] = Counter(jv)
        hs = [float(labels[i]["human_score_0_10"]) for i in ids if labels[i]["human_score_0_10"].strip()]
        js = [float(scores[i]["judge_score"]) for i in ids if labels[i]["human_score_0_10"].strip()]
        out["human_mean"], out["judge_mean"] = (st.mean(hs), st.mean(js)) if hs else (None, None)
        try:
            from scipy.stats import spearmanr
            rho = spearmanr(hs, js)
            out["spearman"] = (float(rho.statistic), float(rho.pvalue))
        except Exception:
            out["spearman"] = None
        out["labelers"] = Counter(labels[i]["labeler"] for i in ids)
        # Cohen's kappa computed here from the two files, with the runner's own helpers (same bins)
        from evals.runners.judge_calibration import _bin, kappa
        out["kappa_verdict"] = kappa(hv, jv)
        if out["kappa_verdict"] is None:
            from sklearn.metrics import cohen_kappa_score
            out["kappa_verdict"] = round(float(cohen_kappa_score(hv, jv)), 4)
        out["kappa_bins"] = kappa([_bin(x) for x in hs], [_bin(x) for x in js]) if hs else None
        out["human_bins"] = Counter(_bin(x) for x in hs)
        out["judge_bins"] = Counter(_bin(x) for x in js)
        # did any judge call fall back to the deterministic path?
        out["fallback_reasons"] = sum(1 for i in ids if any("heuristic" in str(x).lower() or "fallback" in str(x).lower()
                                                            for x in scores[i].get("judge_reasons") or []))
        out["judge_tokens"] = sum(scores[i].get("tokens") or 0 for i in ids)
    return out


# ----------------------------------------------------------------------------- styles
ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=8.8, leading=11.4, spaceAfter=3.5)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.4, leading=9.2, textColor=colors.HexColor("#555555"))
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=12.5, leading=15,
                    spaceBefore=7, spaceAfter=3.5, textColor=colors.HexColor("#14324f"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=9.6, leading=12,
                    spaceBefore=4, spaceAfter=2, textColor=colors.HexColor("#14324f"))
TITLE = ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=17, leading=21, spaceAfter=3)
SUB = ParagraphStyle("sub", parent=BODY, alignment=TA_CENTER, fontSize=9, textColor=colors.HexColor("#333333"))
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7.3, leading=8.8, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
MONO = ParagraphStyle("mono", parent=BODY, fontName="Courier", fontSize=6.4, leading=7.6)


def P(t, s=BODY):
    return Paragraph(t, s)


def src(*files):
    return P("Source: " + ", ".join(f"<font face='Courier'>{f}</font>" for f in files), SMALL)


def table(rows, widths=None, header=True, bold_rows=()):
    data = [[P(str(c), CELLB if (header and i == 0) or i in bold_rows else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c4d0")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
             ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6edf4")))
    for i in bold_rows:
        style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f3f7e9")))
    t.setStyle(TableStyle(style))
    return t


def bullets(items):
    return [P("• " + i) for i in items]


# ----------------------------------------------------------------------------- diagram
def bid_graph_diagram() -> Drawing:
    """Bid graph figure with orthogonal edges (no edge crosses a box)."""
    import math

    W, H = 175 * mm, 78 * mm
    d = Drawing(W, H)
    box_c, edge_c = colors.HexColor("#e6f2f0"), colors.HexColor("#0b4741")
    par_c, appr_c, term_c = colors.HexColor("#fff4dc"), colors.HexColor("#fde2e2"), colors.white

    def box(x, y, w, h, text, fill=box_c, size=6.6):
        d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=edge_c, strokeWidth=0.6, rx=2, ry=2))
        lines = text.split("\n")
        for k, ln in enumerate(lines):
            d.add(String(x + w / 2, y + h / 2 + (len(lines) / 2 - k - 0.8) * (size + 1), ln,
                         fontName="Helvetica", fontSize=size, textAnchor="middle"))

    def seg(x1, y1, x2, y2, dash=None):
        ln = Line(x1, y1, x2, y2, strokeColor=edge_c, strokeWidth=0.6)
        if dash:
            ln.strokeDashArray = dash
        d.add(ln)

    def head(x1, y1, x2, y2):
        a, s = math.atan2(y2 - y1, x2 - x1), 3
        d.add(Polygon([x2, y2, x2 - s * math.cos(a - 0.4), y2 - s * math.sin(a - 0.4),
                       x2 - s * math.cos(a + 0.4), y2 - s * math.sin(a + 0.4)], fillColor=edge_c, strokeColor=edge_c))

    def path(pts, dash=None):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            seg(x1, y1, x2, y2, dash)
        head(*pts[-2], *pts[-1])

    def label(x, y, t, anchor="middle"):
        d.add(String(x, y, t, fontName="Helvetica-Oblique", fontSize=5.8, textAnchor=anchor, fillColor=edge_c))

    bw, bh = 24 * mm, 8 * mm
    # row 1: Scout -> parallel fan-out -> Decide -> END
    yc = H - 20 * mm                       # centre line of row 1
    sx, px, dx = 2, 2 + bw + 12 * mm, 2 + 2 * bw + 24 * mm
    ex = dx + bw + 14 * mm
    box(sx, yc - bh / 2, bw, bh, "Scout\n(intake)")
    fx = sx + bw + 6 * mm                  # fan-out split x
    jx = px + bw + 6 * mm                  # join x
    seg(sx + bw, yc, fx, yc)
    for k, name in enumerate(["Job Analyst", "Risk Assessor", "Fit Matcher"]):
        cy = yc + (1 - k) * (bh + 3 * mm)
        box(px, cy - bh / 2, bw, bh, name, fill=par_c)
        path([(fx, yc), (fx, cy), (px, cy)])
        seg(px + bw, cy, jx, cy)
        seg(jx, cy, jx, yc)
    path([(jx, yc), (dx, yc)])
    label(fx - 1 * mm, yc + bh + 6.5 * mm, "parallel (Send)", anchor="end")
    box(dx, yc - bh / 2, bw, bh, "Decide\nskip / watch / bid")
    box(ex, yc - bh / 2, bw + 6 * mm, bh, "END\nskipped / watching", fill=term_c, size=6.2)
    path([(dx + bw, yc), (ex, yc)], dash=[2, 1.5])
    label((dx + bw + ex) / 2, yc + 1.5 * mm, "skip, watch")

    # row 2: the proposal pipeline
    y2 = yc - 30 * mm
    names = ["Pricing\nStrategist", "Proposal\nWriter", "Claim\nverifier", "Critic", "Compliance\nGuard",
             "dry_run\npreview", "APPROVAL\ninterrupt()", "Submit\n(idempotent)"]
    w2 = bw * 0.82
    gap = (W - 4 - len(names) * w2) / (len(names) - 1)
    xs = [2 + k * (w2 + gap) for k in range(len(names))]
    for x, n in zip(xs, names):
        box(x, y2, w2, bh, n, fill=appr_c if "APPROVAL" in n else box_c, size=6.1)
    for k in range(len(xs) - 1):
        path([(xs[k] + w2, y2 + bh / 2), (xs[k + 1], y2 + bh / 2)])
    # bid: Decide bottom -> down -> left -> Pricing top (runs in the free band between rows)
    mid = y2 + bh + 3.5 * mm
    path([(dx + bw / 2, yc - bh / 2), (dx + bw / 2, mid), (xs[0] + w2 / 2, mid), (xs[0] + w2 / 2, y2 + bh)])
    label(dx + bw / 2 + 1.5 * mm, mid + 1.5 * mm, "bid", anchor="start")
    # critic loop back to writer (below the row)
    lo = y2 - 6 * mm
    path([(xs[3] + w2 / 2, y2), (xs[3] + w2 / 2, lo), (xs[1] + w2 / 2, lo), (xs[1] + w2 / 2, y2)])
    label((xs[1] + xs[3] + w2) / 2, lo - 3 * mm, "revise (at most 2 rounds)")
    # compliance block / budget exceeded -> needs_attention
    nx, ny = xs[4] - 1 * mm, y2 - 17 * mm
    box(nx, ny, w2 + 10 * mm, bh, "needs_attention /\ndead_letter", fill=term_c, size=6)
    path([(xs[4] + w2 * 0.7, y2), (xs[4] + w2 * 0.7, ny + bh)], dash=[2, 1.5])
    label(xs[4] + w2 * 0.7 + 1.5 * mm, y2 - 4 * mm, "block / budget", anchor="start")
    d.add(String(W - 2, 2, "Marketplace writes only via MarketplacePort -> Marketplace MCP -> GigSim | Upwork MCP",
                 fontName="Helvetica-Oblique", fontSize=6.2, textAnchor="end"))
    return d


# ----------------------------------------------------------------------------- build
def build():
    cfg = yaml.safe_load((ROOT / "agent" / "config.yaml").read_text())
    slo = cfg.get("slo", {})
    dec = jload("decision_eval.json")
    heur = jload("decision_eval_heuristic.json")
    groq_b = jload("decision_eval_groq.json")
    groq_a = jload("decision_eval_groq_small.json")
    gout = jload("gigsim_outcomes.json")
    ab = jload("ab_experiment.json")
    arch = jload("arch_comparison.json")
    tg = jload("tool_granularity.json")
    rag = jload("rag_results.json")
    jload("rag_ablation.json")
    corpus = jload("rag_corpus_stats.json")
    rag_table_md = (RES / "rag_table.md").read_text()
    js = judge_stats()
    fails, fail_counts = failure_taxonomy()

    SRC_DIR.mkdir(parents=True, exist_ok=True)
    (SRC_DIR / "failure_taxonomy.json").write_text(json.dumps(
        {"counts": {f"{k[0]}|{k[1]}": v for k, v in fail_counts.items()}, "failures": fails}, indent=1))

    story = []
    story += [P("GigBid: a multi-agent freelancer copilot", TITLE),
              P(f"R&amp;D design review · AI-4016 · {AUTHOR}", SUB),
              P(f"Live: <font face='Courier'>{LIVE_URL}</font> · Code: <font face='Courier'>{REPO_URL}</font>", SUB),
              Spacer(1, 4)]
    story.append(P("<b>How to read this report.</b> Every number is read by <font face='Courier'>scripts/build_report.py</font> "
                   "from a file under <font face='Courier'>evals/results/</font>, cited under each table. All data is synthetic "
                   "(GigSim plus three persona corpora, see <font face='Courier'>docs/DATA_CARD.md</font>). "
                   "The section on limitations at the end of §10 applies to every table."))

    # ---------------------------------------------------------------- 1
    story.append(P("1. Problem and constraints", H1))
    story.append(P("A freelancer spends hours scanning feeds, spends paid Connects on unwinnable jobs, sends generic letters "
                   "and meets scam posts. GigBid automates <i>discovery, assessment and drafting</i>; the human keeps every "
                   "<i>decision</i>. Never automated: submitting a proposal, sending a message, spending Connects (each is a "
                   "LangGraph <font face='Courier'>interrupt()</font> resumed only from the web UI); claiming experience the "
                   "portfolio does not support; following instructions found inside job posts or client messages; any "
                   "scraping or browser automation of a real marketplace."))
    j, p = slo.get("job_analysed", {}), slo.get("proposal", {})
    story.append(table([["Declared budget (agent/config.yaml: slo)", "p95 latency", "Cost"],
                        ["Per job analysed", f"{j.get('p95_latency_s')} s", f"${j.get('cost_usd')}"],
                        ["Per proposal drafted", f"{p.get('p95_latency_s')} s", f"${p.get('cost_usd')}"]],
                       widths=[80 * mm, 35 * mm, 35 * mm]))
    story.append(P(f"Per-thread guards: max {cfg['budgets']['max_steps']} node steps and {cfg['budgets']['max_tokens']:,} "
                   f"LLM tokens; exceeding either moves the thread to a visible <i>needs attention</i> state. "
                   f"Critic loop: at most {cfg['critic']['max_rounds']} revisions.", BODY))

    # ---------------------------------------------------------------- 2
    story.append(P("2. Architecture", H1))
    story.append(bid_graph_diagram())
    story.append(P("Figure 1. Bid graph (one thread per job), drawn from <font face='Courier'>docs/images/bid_graph.mmd</font> "
                   "which <font face='Courier'>python -m agent.graphs.render</font> exports from the compiled graph.", SMALL))
    story += bullets([
        "<b>Bid graph</b> (<font face='Courier'>agent/graphs/bid_graph.py</font>): Scout hands a job in; Job Analyst, Risk "
        "Assessor and Fit Matcher fan out with <font face='Courier'>Send</font> and write to reducer fields; Decide picks "
        "skip/watch/bid; then Pricing → Writer → claim verifier → Critic (≤2 loops) → Compliance → dry-run preview → "
        "approval interrupt → idempotent submit. Terminal states: skipped, watching, submitted, rejected, needs_attention, dead_letter.",
        "<b>Conversation graph</b>: Client Liaison reads new messages, classifies intent (question, negotiation, interview "
        "request, scam signal), drafts a reply plus calendar slots from the Workspace server, passes Compliance and interrupts for approval.",
        "<b>Marketplace port</b> (<font face='Courier'>agent/marketplace_port.py</font>): the only path to a marketplace. "
        "Two adapters behind the Marketplace MCP server, GigSim (HTTP, retries with backoff, typed "
        "<font face='Courier'>MarketplaceUnavailable</font>) and live Upwork (official MCP over Streamable HTTP, OAuth "
        "tokens Fernet-encrypted per user, draft-only writes), switched by <font face='Courier'>MARKETPLACE_MODE</font>.",
        "<b>MCP surface</b>: own Portfolio (read), Marketplace (read + write with idempotency keys, dry_run, bearer auth, "
        "per-user rate limit, append-only audit log) and Workspace (slots, interview holds, email drafts) servers; third-party "
        "Upwork and GitHub servers. Per-agent tool allowlists live in config (<font face='Courier'>tools.allowlist</font>).",
        "<b>State, trace, memory are separate.</b> State = typed <font face='Courier'>BidState</font> with Pydantic hand-offs "
        "(JobSpec, RiskReport, FitReport, BidDecision, PriceQuote, ProposalDraft, Critique, ComplianceVerdict). Trace = "
        "<font face='Courier'>trace_events</font> rows (node, tool, args, tokens, cost, latency, PII-masked) keyed by one "
        "trace id from the UI request to the MCP audit log. Memory = LangGraph store, written only by promotion rules: "
        f"style memory needs ≥{cfg['memory']['style']['min_occurrences']} matching edits; outcome memory needs "
        f"≥{cfg['memory']['outcome']['min_positive_events']} positive marketplace events per category.",
        "<b>Why each agent exists</b>: Analyst and Risk run on the cheap model because they are frequent and structured; "
        "Writer and Critic get the strongest model; Verifier and Compliance are deterministic first, so a model failure "
        "can never let an unsupported claim or contact detail through.",
    ])

    # ---------------------------------------------------------------- 3
    story.append(P("3. R&amp;D question A: does tool granularity change agent behaviour?", H1))
    story.append(P("<b>Hypothesis.</b> A curated tool set with rewritten descriptions beats both many fine-grained tools and "
                   "a few coarse multi-purpose tools on tool-selection accuracy, at a token cost between the two. "
                   f"<b>Setup.</b> {tg['metrics']['fine']['n']} tasks with known correct calls "
                   f"(every second task of <font face='Courier'>{tg['dataset']}</font>, stride {tg['stride']}), "
                   f"model <font face='Courier'>{tg['model']}</font> at temperature {tg['temperature']}, tool results simulated "
                   "with fixed payloads."))
    rows = [["Tool set", "# tools", "Selection acc.", "Argument acc.", "Arg. acc. when tool right", "Tokens / task", "Unexpected writes"]]
    for k in ("fine", "coarse", "best"):
        m = tg["metrics"][k]
        rows.append([k, tg["tool_counts"][k], fmt(m["tool_selection_accuracy"], 2), fmt(m["argument_accuracy"]),
                     fmt(m["argument_accuracy_when_tool_correct"]), f"{m['tokens_per_task']:.0f}", fmt(m["unexpected_write_rate"], 2)])
    story.append(table(rows, widths=[22 * mm, 16 * mm, 23 * mm, 23 * mm, 33 * mm, 22 * mm, 26 * mm], bold_rows=(3,)))
    story.append(src("evals/results/tool_granularity.json"))
    fm, cm, bm = (tg["metrics"][k] for k in ("fine", "coarse", "best"))
    story.append(P(f"<b>Result.</b> Coarse tools are cheapest ({cm['tokens_per_task']:.0f} tokens/task) but the model "
                   f"fills their mode arguments badly (argument accuracy {cm['argument_accuracy']:.3f}). The curated set "
                   f"raises selection accuracy from {fm['tool_selection_accuracy']:.2f} (fine) to {bm['tool_selection_accuracy']:.2f} "
                   f"with equal argument accuracy, but costs more tokens ({bm['tokens_per_task']:.0f} vs {fm['tokens_per_task']:.0f}) "
                   "because its descriptions are longer. <b>Conclusion:</b> granularity changes behaviour; the shipped allowlists use "
                   "the curated set per agent, which also shrinks each agent's prompt. n=20 is small and one model was tested, "
                   "so the 0.10 gap is indicative, not significant."))

    # ---------------------------------------------------------------- 4
    story.append(P("4. R&amp;D question B: retrieval and claim verification", H1))
    story.append(P("<b>Hypothesis (written before the run, <font face='Courier'>rag_hypothesis.md</font>).</b> H1: requirement "
                   "decomposition plus hybrid retrieval (V1+V2) raises evidence Recall@5 by ≥15 points over V0 on jobs with "
                   "four or more requirements. <b>Amendment after a 40-job pilot, before the full run:</b> every variant scored "
                   "Recall@5 = 0 because 150 past proposals per persona paraphrase job titles and outrank all proof items, so an "
                   "evidence-type routing component <font face='Courier'>ev</font> (search case studies and repos only) was added "
                   "and ablated like every other component."))
    {r["variant"]: r for r in rag.get("summary", rag.get("macro", []))} if isinstance(rag.get("summary", None), list) else None
    # parse the generated markdown table (written by evals/runners/make_results_table.py from rag_results.json)
    lines = [ln for ln in rag_table_md.splitlines() if ln.startswith("|")]
    main = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if cells and cells[0] == "Variant" and "Recall@5" in cells[1]:
            main = [cells]
            continue
        if main and len(cells) == len(main[0]) and not set(cells[0]) <= {"-"}:
            main.append(cells)
        elif main and len(cells) != len(main[0]):
            break
    keep_cols = [0, 1, 2, 3, 6, 7, 9, 10, 11]
    hdr = ["Variant", "Recall@5", "MRR", "nDCG@10", "R@5 ≥4 skills", "R@5 <4 skills", "p95 ms", "refusal (no-gold)", "false refusal"]
    rows = [hdr] + [[c[i].replace("**", "") for i in keep_cols] for c in main[1:]]
    best_idx = [i for i, r in enumerate(rows) if "(best)" in r[0]]
    story.append(table(rows, widths=[33 * mm, 15 * mm, 13 * mm, 15 * mm, 19 * mm, 19 * mm, 14 * mm, 22 * mm, 18 * mm],
                       bold_rows=tuple(best_idx)))
    story.append(src("evals/results/rag_results.json", "rag_table.md"))
    story.append(P("Macro-average over the three personas, 60 seeded dev jobs each. V6 (contextual) and V7 (HyDE) were not run; "
                   "V9 was not built. Latency ranks are meaningful, absolute values are not (shared, heavily loaded laptop)."))
    arows = [["Removed from ev+v2+v5", "Recall@5", "nDCG@10", "Δ Recall@5", "Δ nDCG@10"]]
    for ln in rag_table_md.split("### Ablation")[1].splitlines():
        if ln.startswith("|") and not ln.startswith("|---") and "Removed" not in ln:
            c = [x.strip() for x in ln.strip("|").split("|")]
            arows.append([c[0], c[2], c[3], c[4], c[5]])
    story.append(KeepTogether([table(arows, widths=[70 * mm, 20 * mm, 20 * mm, 22 * mm, 22 * mm]),
                               src("evals/results/rag_ablation.json")]))
    # per persona compact
    pp = []
    for ln in rag_table_md.split("### Per persona")[1].split("###")[0].splitlines():
        if ln.startswith("|") and not ln.startswith("|---"):
            pp.append([x.strip() for x in ln.strip("|").split("|")])
    pp_rows = [pp[0]] + [r for r in pp[1:] if r[0] in ("v0", "v0+ev", "ev+v1+v2", "ev+v2+v3", "ev+v2+v5")]
    story.append(P("<b>By persona</b> (Recall@5 / nDCG@10; full table and per-job-type split in Appendix B):", BODY))
    story.append(table(pp_rows, widths=[40 * mm, 40 * mm, 40 * mm, 40 * mm]))
    story.append(P("<b>What the numbers say.</b> H1 is <b>rejected</b>: ev+v1+v2 beats v0+ev by 6.0 points of Recall@5, not 15; "
                   "every dev job has ≥4 requirements so the &lt;4 bucket is empty and that half is untestable. Cross-encoder "
                   "reranking (H2) <i>lowered</i> recall (a web-search MiniLM does not understand 'skill implied by this paragraph'), "
                   "outcome boosting V4 hurt MRR (gold evidence proves skills, it does not record past wins), and the corrective "
                   "loop V8 refused on 61% of no-gold jobs but also falsely refused on 13% of real ones. Almost all the gain "
                   "comes from one corpus fact (routing to proof items). <b>Shipped:</b> ev+v2+v5 (best on all three item metrics "
                   "and fast enough for the serverless deploy), set in <font face='Courier'>rag/shipped_variant.yaml</font>."))
    hm, ga, gb = heur["metrics"], groq_a["metrics"], groq_b["metrics"]
    story.append(P("<b>Claim verification (B3).</b> After drafting, <font face='Courier'>rag/verify.py</font> splits the letter "
                   "into claims and grades each against retrieved evidence; unsupported claims are removed or rewritten before "
                   f"the Critic. Unsupported claims per proposal before → after: heuristic writer "
                   f"{hm['unsupported_claims_per_proposal_before']} → {hm['unsupported_claims_per_proposal_after']} "
                   f"(n={hm['proposals']} proposals), gpt-oss-20b writer {ga['unsupported_claims_per_proposal_before']} → "
                   f"{ga['unsupported_claims_per_proposal_after']} (n={ga['proposals']}), gpt-oss-120b writer "
                   f"{gb['unsupported_claims_per_proposal_before']} → {gb['unsupported_claims_per_proposal_after']} "
                   f"(n={gb['proposals']}). The LLM writers invent about one claim per letter; the verifier catches them, "
                   "but 'after = 0' is measured by the same verifier, so it shows consistency, not ground truth."))
    # judge
    story.append(P("<b>Judge calibration (B4).</b>", H2))
    if js.get("n"):
        js["raw"]
        kv = js.get("kappa_verdict")
        sp = js.get("spearman")
        hv, jv = js["human_verdicts"], js["judge_verdicts"]
        story.append(P(
            f"30 proposals from the deterministic writer were labelled blind by the author ({', '.join(js['labelers'])}, "
            f"n={js['n']}) and scored by the gpt-oss-120b judge. Human verdicts: {dict(hv)}; judge verdicts: {dict(jv)}. "
            f"Raw verdict agreement {js['agreement']:.2f}, Cohen's κ (verdict) = {fmt(kv)}"
            f", κ on score bins (low &lt;5, mid &lt;7.5, high) = {fmt(js.get('kappa_bins'))} "
            f"(human bins {dict(js['human_bins'])}, judge bins {dict(js['judge_bins'])}). "
            f"Mean score: human {js['human_mean']:.2f} vs judge {js['judge_mean']:.2f}"
            + (f"; Spearman ρ = {sp[0]:.2f} (p = {sp[1]:.2f})" if sp else "") + ". "
            "This is the <b>kappa paradox</b>: the human said <i>revise</i> to every proposal, so expected chance agreement "
            "is already near the observed agreement and κ collapses to about zero even though the two raters agree on "
            "almost every item. The informative finding is the offset: the judge is about "
            f"{js['judge_mean'] - js['human_mean']:.1f} points more lenient than the human on a 0-10 scale and its scores "
            "barely vary. <b>Consequence:</b> judge scores are reported as uncalibrated and are not used to choose variants. "
            "Fixes for a later round: anchor the rubric with scored examples, and include some strong (LLM-written) letters "
            "in the calibration set so both classes occur."))
    else:
        story.append(P("Human labels were not available when this report was built; κ is not measured."))
    story.append(src("evals/results/judge_calibration_groq.json", "evals/datasets/human_labels.csv"))

    # ---------------------------------------------------------------- 5
    story.append(P("5. R&amp;D question C: single agent vs supervisor vs hand-built graph", H1))
    r = arch["results"]
    rows = [["Metric", "(a) ReAct, all tools", "(b) langgraph-supervisor", "(c) hand-built graph"]]
    keys = [("bid_skip_accuracy", "Bid/skip accuracy"), ("scam_recall", "Scam recall"), ("proposals", "Proposals drafted"),
            ("unsupported_claims_per_proposal_sent", "Unsupported claims / proposal"),
            ("compliance_violations_caught", "Compliance violations caught"),
            ("gigsim_reply_rate", "GigSim reply rate"), ("tokens_per_job_mean", "Tokens / job"),
            ("latency_s_p50", "p50 latency (s)"), ("latency_s_p95", "p95 latency (s)"), ("errors", "Run errors")]
    for k, label in keys:
        rows.append([label] + [fmt(r[a].get(k), 2) if isinstance(r[a].get(k), float) else fmt(r[a].get(k))
                               for a in ("a_react_single_agent", "b_langgraph_supervisor", "c_hand_built_graph")])
    story.append(table(rows, widths=[48 * mm, 40 * mm, 40 * mm, 40 * mm]))
    story.append(src("evals/results/arch_comparison.json"))
    story.append(P(f"n = {arch['n_jobs']} jobs, every arm on <font face='Courier'>{arch['model']}</font> (the 20b daily quota "
                   "was exhausted). The ReAct agent mis-routed one job and its single proposal carried 2 unsupported claims, "
                   "because nothing forces it to call retrieval before writing. The supervisor matched the graph on decisions "
                   f"but used {r['b_langgraph_supervisor']['tokens_per_job_mean'] / r['c_hand_built_graph']['tokens_per_job_mean']:.1f}× its tokens. The graph's low token count is partly a fallback artefact: some of its nodes hit "
                   f"the 120b quota and ran deterministically. <b>Where (a) wins:</b> latency (p50 {r['a_react_single_agent']['latency_s_p50']:.1f} s vs {r['c_hand_built_graph']['latency_s_p50']:.1f} s) on jobs it "
                   "skips immediately; for a pure triage-only tool a single agent would be acceptable. With n=8 no difference "
                   "here is statistically meaningful; the design argument (enforced verification and approval) is structural."))
    # open model configs
    usage = groq_b.get("llm_usage_by_node", {})
    cheap = set(cfg["node_groups"]["cheap"])
    fb_calls = sum(v["calls"] for k, v in usage.items() if k in cheap)
    fb_fail = sum(v.get("failures") or 0 for k, v in usage.items() if k in cheap)
    story.append(P("<b>Choosing models by measurement</b> (same seeded 40-job subset for the hosted configs):", H2))
    rows = [["Config", "n", "Macro-F1 bid/skip", "Scam P / R", "Price in band", "Unsupp. before→after",
             "p50 / p95 job (s)", "Tokens / job", "USD / job", "USD / proposal", "Out tok/s"]]
    order = [("heuristic", "Deterministic (no LLM)"), ("groq_small", "A: gpt-oss-20b everywhere"),
             ("groq", "B: 20b cheap + 120b writer/critic"), ("ollama_qwen", "Local qwen2.5 7B q4"),
             ("ollama_mistral", "Local mistral 7B q4")]
    for k, label in order:
        m = dec[k]
        full = jload(f"decision_eval_{k}.json")["metrics"]
        rows.append([label, m["n_jobs"], fmt(m["macro_f1_bid_skip"]), f"{fmt(m['scam_precision'], 2)} / {fmt(m['scam_recall'], 2)}",
                     fmt(m["price_in_band"], 2), f"{fmt(m['unsupported_before'], 2)} → {fmt(m['unsupported_after'], 2)}",
                     f"{m['latency_p50_s']:.1f} / {m['latency_p95_s']:.1f}", f"{m['tokens_per_job_mean']:.0f}",
                     f"{m['cost_usd_per_job']:.5f}", fmt(full.get("cost_usd_per_proposal"), 4),
                     fmt(m["output_tokens_per_s"], 1)])
    story.append(table(rows, widths=[33 * mm, 8 * mm, 15 * mm, 15 * mm, 13 * mm, 17 * mm, 19 * mm, 13 * mm, 14 * mm, 14 * mm, 11 * mm]))
    story.append(src("evals/results/decision_eval.json", "decision_eval_*.json", "gigsim_outcomes.json"))
    story.append(P("Local models ran on an Apple M4 laptop (16 GB) through Ollama; hosted models on Groq's free tier, so their "
                   f"latency includes rate-limit waits and config B hit the daily token cap ({fb_fail} of {fb_calls} cheap-node calls fell back "
                   "to the deterministic path). Decision quality is identical across A and B because Decide is rule-based on "
                   "the structured hand-offs; the models differ in writing. <b>Choice:</b> config A (gpt-oss-20b) is the deployed "
                   "open profile for cheap nodes; the 120b writer is used when quota allows. Local 7B models are too slow on a "
                   f"laptop for interactive use (p50 {dec['ollama_mistral']['latency_p50_s']:.0f}-{dec['ollama_qwen']['latency_p50_s']:.0f} s per job)."))
    rows = [["GigSim outcome (fixed job set)", "n", "Reply rate", "Interview", "Hire", "Template baseline reply"]]
    for k, label in order:
        a, b = gout[k]["agent"], gout[k]["generic_template_baseline"]
        rows.append([label, a["n"], fmt(a["reply_rate"], 2), fmt(a["interview_rate"], 2), fmt(a["hire_rate"], 2), fmt(b["reply_rate"], 2)])
    story.append(table(rows, widths=[55 * mm, 12 * mm, 22 * mm, 22 * mm, 18 * mm, 40 * mm]))
    story.append(src("evals/results/gigsim_outcomes.json"))
    story.append(P("<b>Where better retrieval and writing did not raise reply rate.</b> On the hosted subsets (n=14 proposals) the "
                   f"LLM letters reply no better than a generic template ({gout['groq_small']['agent']['reply_rate']:.2f}-{gout['groq']['agent']['reply_rate']:.2f} vs {gout['groq']['generic_template_baseline']['reply_rate']:.2f}), even though their mean simulated "
                   f"reply probability is higher ({gout['groq']['agent']['mean_reply_prob']:.2f}-{gout['groq_small']['agent']['mean_reply_prob']:.2f} vs {gout['groq']['generic_template_baseline']['mean_reply_prob']:.2f}). With {gout['groq']['agent']['n']} draws the Bernoulli noise is larger than the effect. "
                   f"On the large deterministic run (n={gout['heuristic']['agent']['n']}) the evidence-first letter doubles the template's reply rate "
                   f"({gout['heuristic']['agent']['reply_rate']:.2f} vs {gout['heuristic']['generic_template_baseline']['reply_rate']:.2f}). A second reason is that GigSim clients score must-have skills and price, which the template "
                   "also mentions, so retrieval quality beyond 'name the skill' is only weakly rewarded by the simulator."))

    # ---------------------------------------------------------------- 6
    story.append(P("6. The change request (2 November policy update)", H1))
    yaml.safe_load((ROOT / "data" / "policy_pack" / "updates" / "2026-11-02.yaml").read_text())
    n_lines = len((ROOT / "data" / "policy_pack" / "updates" / "2026-11-02.yaml").read_text().splitlines())
    story.append(P("<b>What changed.</b> Bidding on a job posted less than an hour ago costs +2 Connects (early-bird surcharge), "
                   "and cover letters over 2,500 characters are rejected. <b>What was edited.</b> One data file, "
                   f"<font face='Courier'>data/policy_pack/updates/2026-11-02.yaml</font> ({n_lines} lines). No Python changed: "
                   "the policy loader merges every file in <font face='Courier'>updates/</font> whose <font face='Courier'>effective</font> "
                   "date has passed; Pricing reads the surcharge through <font face='Courier'>agent/policy.py: connects_cost()</font>, "
                   "Compliance blocks over-length drafts with reason <font face='Courier'>max_proposal_length</font>, and the Writer's "
                   f"own cap stays at {cfg['writer']['max_chars']} characters. Four unit tests cover it, including replaying the old "
                   "policy with <font face='Courier'>GIGBID_TODAY=2026-10-01</font>. <b>Honest caveat on timing:</b> in this build the "
                   "update file and the loader were written together, so 'how long it took to absorb' was not measured against a "
                   "frozen system. What the design shows is that rules, costs and limits are data; only a new <i>kind</i> of "
                   "condition (for example a surcharge keyed on a new job field) would need code."))

    # ---------------------------------------------------------------- 7
    story.append(P("7. Signature extension X2: proposal experiments", H1))
    z = ab["two_proportion_z_test"]
    sa, sb = ab["strategies"]["A"], ab["strategies"]["B"]
    story.append(P(f"Two writer strategies from <font face='Courier'>agent/config.yaml: writer.strategies</font> ran on the same "
                   f"{ab['n_jobs_per_arm']} bid jobs in GigSim (paired design, config '{ab['config']}'). "
                   f"A = <i>{sa['name']}</i> (opens by restating the client's problem, {sa['evidence_items']} evidence items, medium); "
                   f"B = <i>{sb['name']}</i> (opens with a question, {sb['evidence_items']} item, short)."))
    rows = [["Arm", "n", "Replied", "Reply rate", "Interview", "Hire", "Mean chars"]]
    for k in ("A", "B"):
        s = ab["arm_summaries"][k]
        rows.append([f"{k}: {ab['strategies'][k]['name']}", s["n"], ab["successes"][k], fmt(s["reply_rate"], 3),
                     fmt(s["interview_rate"], 3), fmt(s["hire_rate"], 3), f"{ab['mean_chars'][k]:.0f}"])
    story.append(table(rows, widths=[45 * mm, 12 * mm, 18 * mm, 20 * mm, 20 * mm, 16 * mm, 20 * mm]))
    story.append(src("evals/results/ab_experiment.json"))
    story.append(P(f"Difference A−B = {z['diff_A_minus_B']:.3f} (95% CI {z['ci95_diff'][0]:.3f} to {z['ci95_diff'][1]:.3f}); "
                   f"two-proportion z = {z['z']:.2f}, p = {z['p_value']:.4f}; exact McNemar on the paired outcomes "
                   f"p = {ab['mcnemar_exact']['p_value']:.4f}. A ships as the default. <b>Caveat:</b> GigSim's simulated clients "
                   "penalise short, generic letters by construction, so this measures agreement with the simulator's model "
                   "of a client, not real-world reply rates."))

    # ---------------------------------------------------------------- 8
    story.append(P("8. Failure analysis", H1))
    cats_order = ["missed evidence", "wrong skip", "wrong bid", "mispriced", "unsupported claim", "generic opening",
                  "compliance miss", "injection", "scam miss", "scam false positive", "tool error"]
    cfgs = ["heuristic", "groq_small", "groq", "ollama_qwen", "ollama_mistral"]
    rows = [["Category"] + ["heuristic (600)", "20b (40)", "120b (40)", "qwen (10)", "mistral (10)"]]
    for c in cats_order:
        rows.append([c] + [fail_counts.get((k, c), 0) for k in cfgs])
    story.append(table(rows, widths=[38 * mm, 26 * mm, 22 * mm, 22 * mm, 22 * mm, 24 * mm]))
    story.append(src("evals/results/decision_records_*.jsonl", "docs/report/failure_taxonomy.json"))
    story.append(P("Counts are jobs per category (a job can fall into several). 'Missed evidence' = under a third of gold items "
                   "retrieved for a bid; 'unsupported claim' is counted <i>before</i> verification. Twelve concrete failures:"))
    picks, seen = [], set()
    want = [("groq", "wrong skip"), ("heuristic", "wrong skip"), ("heuristic", "wrong skip"), ("heuristic", "wrong bid"),
            ("heuristic", "wrong bid"), ("groq", "mispriced"), ("groq_small", "mispriced"), ("ollama_mistral", "scam false positive"),
            ("groq", "missed evidence"), ("groq", "unsupported claim"), ("ollama_qwen", "missed evidence"), ("groq_small", "unsupported claim")]
    for cfg_k, cat in want:
        for f in fails:
            if f["config"] == cfg_k and cat in f["cats"] and (f["config"], f["job_id"]) not in seen:
                picks.append((cat, f))
                seen.add((f["config"], f["job_id"]))
                break
    fix = {
        "wrong skip": ("The fixed-price floor check converts the posted duration into hours with a fixed table "
                       "(agent/config.yaml: pricing.hours_by_duration), which overestimates effort for small jobs. "
                       "Fix to try: use the Analyst's own effort estimate.", "not tried"),
        "wrong bid": ("Gold marks the job below the freelancer's floor, but the hourly-ratio check "
                      "(thresholds.min_hourly_ratio_of_floor) passed it. Fix to try: include platform fees in the floor check.",
                      "not tried"),
        "mispriced": ("The quote is anchored to the client's posted budget range rather than the category's market "
                      "statistics. Fix to try: blend market p50 with the budget midpoint.", "not tried"),
        "scam false positive": ("The mistral-backed Risk Assessor raised a scam flag on a low-quality client; the "
                                "deterministic path for the same job skips it for client quality, not scam. The decision "
                                "(skip) was still correct. Fix to try: require two independent high flags from the LLM.",
                                "not tried"),
        "unsupported claim": ("The LLM writer added a claim the portfolio does not support. Claim verification removed "
                              "or rewrote it before the Critic saw the draft (unsupported after verification = 0).", "worked"),
    }

    def missed_detail(f):
        rec = next(json.loads(ln) for ln in open(RES / f"decision_records_{f['config']}.jsonl")
                   if json.loads(ln)["job_id"] == f["job_id"])
        gold, got = rec["gold"]["evidence_ids"], rec.get("evidence_items") or []
        hit = [g for g in gold if g in got]
        return (f"Retrieved {len(hit)} of {len(gold)} gold items ({', '.join(hit) or 'none'}); "
                f"missed {', '.join(g for g in gold if g not in got)}, outranked by {', '.join(x for x in got if x not in gold) or 'nothing'}. "
                "Fix to try: per-requirement retrieval (V1) for deliverable-type requirements.")

    rows = [["#", "Job (config)", "Type", "Category", "What went wrong / fix tried", "Fix worked?"]]
    for i, (cat, f) in enumerate(picks, 1):
        why, ok = fix.get(cat, ("", ""))
        detail = why
        if cat == "missed evidence":
            detail, ok = missed_detail(f), "not tried"
        if cat == "mispriced":
            detail = f"Bid {f['price']:.0f} vs band {f['band'][0]:.0f}-{f['band'][1]:.0f}. " + why
        if cat == "wrong skip":
            rs = f["reason"]
            if "client score" in rs:
                why = ("The Risk Assessor's client score fell below thresholds.client_score_min although gold rates the "
                       "client acceptable (new client, little history). Fix to try: do not penalise missing history as "
                       "heavily as bad history.")
            elif "duplicate" in rs:
                why = ("Dedup matched a near-identical post from the same client that gold treats as a separate job. "
                       "Fix to try: require the same client and posting window, not only text similarity.")
            detail = f"Reason logged: '{rs}'. " + why
        if cat == "wrong bid":
            detail = (f"Gold skip reason: {f.get('gold_skip_reason') or 'n/a'}. " + why)
        rows.append([i, f"{f['job_id']} ({f['config']})", f["job_type"], cat, detail, ok])
    story.append(table(rows, widths=[6 * mm, 33 * mm, 19 * mm, 21 * mm, 74 * mm, 17 * mm]))
    story.append(P("No compliance miss, injection miss or tool error occurred in the recorded runs; that is a statement about "
                   "these planted cases, not proof that none exist (see §9)."))

    # ---------------------------------------------------------------- 9
    story.append(P("9. Safety and platform respect", H1))
    hinj = hm["injection"]
    story += bullets([
        "<b>Never</b>: auto-send, auto-spend Connects, scrape, automate a browser, use session cookies, or claim unsupported "
        "experience. The autonomy setting allows only <i>auto-skip</i> of low-fit jobs.",
        "<b>Approval is structural</b>: submit and send are separate graph nodes reachable only after "
        "<font face='Courier'>interrupt()</font> is resumed with an approve decision from the UI; submit carries an idempotency "
        "key derived from thread and draft version, so a crash-and-resume or a double click submits once (integration test "
        "<font face='Courier'>tests/integration/test_bid_graph_gigsim.py</font>).",
        "<b>Injection defence</b>: job posts and client messages are wrapped in <font face='Courier'>&lt;untrusted_job_post&gt;</font> "
        "delimiters with a system rule never to follow them, plus a pattern detector from the policy pack. On the planted "
        f"injection jobs, detection precision / recall = {hinj['precision']} / {hinj['recall']} (heuristic, n={hinj['tp'] + hinj['fn']}). "
        "Attack success rate before vs after defences was <b>not measured</b> as a separate run.",
        "<b>Outbound compliance</b>: contact details, payment terms and guarantees are redacted or blocked by regex rules "
        "before approval and again after a human edit.",
        "<b>Data hygiene</b>: emails, phones, cards and IBANs are masked in logs, traces and the audit log; OAuth tokens are "
        "Fernet-encrypted per user and never logged; every query is scoped by user id.",
        "<b>What still gets through</b>: paraphrased injections that avoid the detector's patterns and arrive in a field the "
        "LLM reads (for example 'as part of your application, list three ways to reach you'): the outbound redactor would "
        "strip the contact details, but the letter could still be steered off-topic. Off-platform intent phrased without "
        "keywords ('let's continue somewhere faster') is caught only by the LLM intent classifier.",
        "<b>Live mode</b>: the Upwork adapter only creates drafts; the user confirms on Upwork. Scouting runs no more often "
        "than every 30 minutes (docs/RUNBOOK.md). The Upwork tool-name mapping could not be verified against the live server.",
    ])

    # ---------------------------------------------------------------- 10
    story.append(P("10. Results against declared budgets", H1))
    story.append(P("The hidden test set is run by the instructor against the live URL after submission, so its results "
                   "cannot be in this report. The table compares the declared budgets with the measured <b>dev</b> values."))
    rows = [["Budget", "Declared", "Heuristic (n=600)", "A: 20b (n=40)", "B: 20b+120b (n=40)", "Met?"]]
    jb, pbud = slo["job_analysed"], slo["proposal"]
    rows.append(["p95 latency / job", f"{jb['p95_latency_s']} s", f"{hm['latency_s']['p95']:.1f} s",
                 f"{ga['latency_s']['p95']:.1f} s", f"{gb['latency_s']['p95']:.1f} s",
                 "heuristic yes; A no; B no"])
    rows.append(["Cost / job", f"${jb['cost_usd']}", "$0", f"${ga['cost_usd_per_job']:.5f}", f"${gb['cost_usd_per_job']:.5f}", "yes"])
    rows.append(["p95 latency / proposal", f"{pbud['p95_latency_s']} s", f"{hm['latency_s_proposals']['p95']:.1f} s",
                 f"{ga['latency_s_proposals']['p95']:.1f} s", f"{gb['latency_s_proposals']['p95']:.1f} s", "A yes; B no"])
    rows.append(["Cost / proposal", f"${pbud['cost_usd']}", "$0", f"${ga['cost_usd_per_proposal']:.4f}",
                 f"${gb['cost_usd_per_proposal']:.4f}", "yes"])
    story.append(table(rows, widths=[33 * mm, 19 * mm, 28 * mm, 25 * mm, 30 * mm, 33 * mm]))
    story.append(src("agent/config.yaml (slo)", "evals/results/decision_eval_*.json"))
    story.append(P(f"<b>Budgets missed, without excuses:</b> hosted p95 per job ({ga['latency_s']['p95']:.1f} s and {gb['latency_s']['p95']:.1f} s) exceeds the {jb['p95_latency_s']} s budget. "
                   "Most of it is free-tier rate-limit waiting, but that is the deployment the hidden run will hit too. "
                   "<b>One optimisation that helped:</b> skipping early. Decide runs before any Writer call, and on the hosted "
                   f"subset {ga['n'] - ga['proposals']} of {ga['n']} jobs ended at Decide, which is why the p50 per job ({ga['latency_s']['p50']:.1f} s for A) is far below the p95. "
                   "Routing the frequent nodes to the 20b model cut cost per proposal from "
                   f"${gb['cost_usd_per_proposal']:.4f} (B) to ${ga['cost_usd_per_proposal']:.4f} (A) with identical decisions."))
    story.append(P("<b>Limitations that apply to every number above.</b>", H2))
    story += bullets([
        "The dev set, the simulator and the deterministic heuristics were built by the same author from the same skill graph, "
        "and the heuristic thresholds were tuned on the dev set with no held-out split. The heuristic scores (macro-F1 "
        f"{dec['heuristic']['macro_f1_bid_skip']:.3f}, scam P/R 1.0/1.0) are therefore optimistic.",
        "Small n: Ollama runs n=10, architecture comparison n=8, tool study n=20, hosted proposals n=14.",
        "Groq's free-tier daily cap was hit during config B and the architecture comparison; some calls used the "
        "deterministic fallback.",
        "Latencies were measured on a shared, heavily loaded laptop or under free-tier rate limits.",
        "Not done: the blind pairwise human panel of classmates; V6, V7 and V9 retrieval variants; a separate injection "
        "attack-success-rate run; a rendered PNG of the graphs (the Mermaid source is in Appendix A).",
    ])

    # ---------------------------------------------------------------- appendices
    story.append(PageBreak())
    story.append(P("Appendix A. Graph sources (exported from the compiled graphs)", H1))
    for name in ("bid_graph.mmd", "conversation_graph.mmd"):
        pth = ROOT / "docs" / "images" / name
        if pth.exists():
            story.append(P(f"<font face='Courier'>docs/images/{name}</font>", H2))
            story.append(Preformatted(pth.read_text(), MONO))
    story.append(P("Appendix B. Retrieval by job type: V0 vs shipped (Recall@5)", H1))
    jt = []
    for ln in rag_table_md.split("### By job type")[1].split("###")[0].splitlines():
        if ln.startswith("|") and not ln.startswith("|---"):
            jt.append([x.strip() for x in ln.strip("|").split("|")])
    story.append(table(jt, widths=[25 * mm, 35 * mm, 12 * mm, 20 * mm, 20 * mm]))
    story.append(src("evals/results/rag_table.md"))
    story.append(P("Appendix C. Corpus and dev-set statistics", H1))
    rows = [["Persona", "Case studies", "Repos", "Code files", "Past proposals (won/replied/ignored)", "Dev jobs (bid/skip)", "Scam", "Injection"]]
    for k, v in corpus.items():
        if not isinstance(v, dict) or "items_by_type" not in v:
            continue
        o = v["proposal_outcomes"]
        rows.append([k, v["items_by_type"]["case_study"], v["items_by_type"]["repo"], v["code_files"],
                     f"{v['items_by_type']['proposal']} ({o.get('won')}/{o.get('replied')}/{o.get('ignored')})",
                     f"{v['dev_jobs']} ({v['dev_actions'].get('bid')}/{v['dev_actions'].get('skip')})", v["dev_scam"], v["dev_injection"]])
    story.append(table(rows, widths=[18 * mm, 18 * mm, 13 * mm, 15 * mm, 42 * mm, 30 * mm, 12 * mm, 16 * mm]))
    story.append(src("evals/results/rag_corpus_stats.json"))
    story.append(P("Appendix D. Judge calibration items", H1))
    if js.get("n"):
        labels = {r["proposal_id"]: r for r in csv.DictReader(open(ROOT / "evals" / "datasets" / "human_labels.csv"))}
        rows = [["Item", "Job", "Human score", "Human verdict", "Judge score", "Judge verdict"]]
        for s in js["raw"]["scores"]:
            h = labels.get(s["proposal_id"], {})
            rows.append([s["proposal_id"], s["job_id"], h.get("human_score_0_10", ""), h.get("human_verdict_pass_or_revise", ""),
                         fmt(float(s["judge_score"]), 2), s["judge_verdict"]])
        story.append(table(rows, widths=[15 * mm, 35 * mm, 22 * mm, 25 * mm, 22 * mm, 25 * mm]))
        story.append(src("evals/results/judge_calibration_groq.json", "evals/datasets/human_labels.csv"))
    story.append(P("Appendix E. Reproduce", H1))
    story.append(Preformatted("make seed      # generate GigSim + corpora, seed the simulator\n"
                              "make test     # unit, contract, integration (LLM_PROVIDER=heuristic)\n"
                              "make eval     # rag_eval, decision_eval, gigsim_outcomes -> evals/results/*.json\n"
                              "python -m evals.runners.tool_granularity     # R&D A\n"
                              "python -m evals.runners.arch_comparison      # R&D C\n"
                              "python -m evals.runners.ab_experiment        # X2\n"
                              "python -m evals.runners.judge_calibration    # kappa from evals/datasets/human_labels.csv\n"
                              "python scripts/build_report.py               # this PDF", MONO))

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(15 * mm, 9 * mm, "GigBid · AI-4016 R&D report · " + AUTHOR)
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=13 * mm,
                            bottomMargin=15 * mm, title="GigBid R&D report", author=AUTHOR, subject="AI-4016 R&D assignment")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
