# R&D question B: hypothesis (written before any variant was run)

**H1 (primary).** Requirement decomposition plus hybrid BM25+dense retrieval (V1+V2) raises evidence
Recall@5 by at least 15 points over the naive dense baseline V0 on dev jobs with four or more
requirements, macro-averaged over the three personas.

**H2.** Cross-encoder reranking (V3) on top of V1+V2 adds at least 3 points of nDCG@10 (precision at
small k), at a p95 latency cost below 1 s per job on a laptop CPU.

**H3.** Outcome-aware boosting (V4) changes item-level retrieval metrics by less than 2 points either
way: gold evidence is labelled by "proves the requirement", not by "won before", so any value of V4
should show up in GigSim reply rate rather than in Recall@5.

**H4.** Multi-vector items (V5) help most on the persona whose repos hide skills in code (README does
not name them), and help less than V1/V2 overall.

**H5.** The corrective loop (V8) returns no evidence on a meaningful share of jobs without gold
evidence (off-profile / skip jobs), at the cost of some false refusals and lower recall on real jobs.

Falsification: if V1+V2 does not beat V0 by 15 points of Recall@5 on >=4-requirement jobs, H1 is
rejected and reported as such in rag_decision.md.

Protocol: `python -m evals.runners.rag_eval` on evals/datasets/dev_{aiml,fullstack,data}.jsonl,
item-level metrics against gold `evidence_ids`, k=10, fixed seed 42, all variants from one config
(rag/config.yaml `variants`).

## Amendment after a 40-job aiml pilot (before the full run)

The pilot showed every variant at Recall@5 = 0 when searching the whole corpus: the 150 past
proposals per persona paraphrase job titles and outrank every case study and repo, while gold
evidence consists only of case studies and repos. An evidence-type routing component `ev` (search
proof items only; proposals stay reachable with `filters={"type": "proposal"}` and feed V4's outcome
statistics) was added and is ablated like every other component. H1 is therefore tested as
`ev+v1+v2` vs `v0+ev` (same routing, naive retrieval) as well as vs plain `v0`. The pilot also
used to calibrate V8's cross-encoder thresholds (30 aiml jobs) and the whole-post weight in V1's
fusion (3.0); those jobs are part of the dev set, so V8/V1 numbers are mildly optimistic.
Multi-requirement rerank combinations (`ev+v1+v2+v3`) took ~8 s/job on the shared, heavily loaded
machine and are excluded from the full grid for time.
