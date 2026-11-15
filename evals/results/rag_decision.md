# Decision: what retrieval ships

**Ship `ev+v2+v5`: evidence-type routing + hybrid BM25/dense with RRF + multi-vector items** (set in
`rag/shipped_variant.yaml`). On the seeded 60-job-per-persona dev sample (`rag_results.json`), it has
the best macro Recall@5 (0.605), MRR (0.977) and nDCG@10 (0.777), against 0.012 / 0.034 / 0.025 for V0.
Almost all of that gap comes from one corpus fact: 150 past proposals per persona paraphrase job
titles and swamp naive search, while proof lives in case studies and repos. Routing alone (`v0+ev`)
reaches Recall@5 0.522, and removing `ev` from the shipped pipeline drops Recall@5 by 0.605
(`rag_ablation.json`). The other ablations: dropping hybrid costs 0.042 Recall@5 and 0.044 nDCG@10,
and dropping multi-vector costs 0.011 / 0.021. Both gains are small but hold across personas.

H1 is **rejected**. `ev+v1+v2` beats `v0+ev` by 6.0 points of Recall@5 (0.582 vs 0.522), short of the
15 points predicted. Every dev job has at least 4 requirements, so the "<4" bucket is empty and that
part of the hypothesis cannot be tested. Requirement decomposition on its own added nothing over `ev`
(0.547 vs 0.547) and made `ev+v2` worse (0.582 vs 0.594). Several more hypotheses also failed:
- **Reranking (H2).** Cross-encoder reranking with ms-marco MiniLM lowered Recall@5 (`ev+v2+v3` 0.522
  vs `ev+v2` 0.594) and cost seconds per job. The web-search reranker does not understand "skill
  implied by this paragraph".
- **Outcome boosting (H3).** It hurt more than predicted: `ev+v4` scored 0.514 vs 0.547 Recall@5, and
  MRR fell from 0.909 to 0.792. Gold evidence is about proving skills, not about past wins.
- **Corrective loop (H5).** V8 refused on 61% of jobs that have no gold evidence. It also falsely
  refused on 13% of real jobs and dropped Recall@5 to 0.449. So it does not ship as the retriever, but
  its refusal signal is a candidate input to the skip decision.

Latencies are not reliable: the runs shared a laptop at load average 25-100 with other evaluation
jobs, so only their order (dense ≈ hybrid < decomposition < reranking) should be read. Whether better
retrieval improves GigSim reply rate is **not measured** by this runner. The outcome runners have to
answer that, and V4's drop in item metrics does not rule out a gain in reply rate.
