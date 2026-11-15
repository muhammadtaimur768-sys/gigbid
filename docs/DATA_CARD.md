# Data card: GigBid persona corpora and dev sets

All counts below come from `evals/results/rag_corpus_stats.json`, written by
`python -m evals.runners.rag_eval` (function `corpus_stats`). Re-run it to refresh them.

## Provenance

- **Fully synthetic.** Every persona file, job post and gold label is produced by `gigsim/generate.py`
  (`python -m gigsim.generate`), deterministic with random seed 42. No real freelancer, client or
  job data is included. Names of people and companies are invented.
- One skill/project graph per persona (`gigsim/vocab.py`) is the single source for the portfolio,
  the job stream and the gold labels, so gold evidence ids are correct by construction rather than
  hand-labelled.
- Licence/consent: no personal data; nothing to consent to. Safe to commit.

## Persona corpora (`data/personas/{aiml,fullstack,data}/`)

| Persona | CV | Case studies | Repos (code files) | Reviews | Past proposals (won / replied / ignored) | Chunks fixed / structured / multi-vector |
|---|---|---|---|---|---|---|
| aiml (AI/ML engineer) | 1 | 19 | 6 (12) | 12 | 150 (31 / 49 / 70) | 259 / 238 / 432 |
| fullstack (full-stack web dev) | 1 | 18 | 7 (18) | 12 | 150 (51 / 39 / 60) | 262 / 243 / 438 |
| data (data analyst) | 1 | 17 | 5 (14) | 12 | 150 (44 / 36 / 70) | 252 / 232 / 422 |

Files: `profile.json`, `cv.md` + `cv.pdf` (PDF rendered from the Markdown with reportlab; the loader
prefers the PDF via pypdf), `case_studies/*.md` (YAML frontmatter: id, title, project, skills, date,
client_industry, outcome), `repos/<id>/README.md` + `src/*` code, `reviews.json`, `proposals.jsonl`
(with outcome won|replied|ignored), and `manifest.json` (metadata for every item; used to fill
repo metadata that the README does not carry).

Built-in difficulty (by design of the generator):
- Skills are often **implied, not named** ("We trained small low-rank adapters..." instead of "LoRA").
- The **same project is described three ways** (case study, repo README, code).
- **Code reveals skills the README does not name** (imports such as `peft`, `qdrant_client`).
- **Past proposals paraphrase job titles** and dominate naive retrieval although they are not proof;
  their outcome matters more than their wording.

## Dev sets (`evals/datasets/dev_{persona}.jsonl`)

| Persona | Jobs | Gold bid / skip | Scam | Prompt injection | Jobs with gold evidence | Mean gold items per such job | Gold evidence: case / repo | Distinct job types |
|---|---|---|---|---|---|---|---|---|
| aiml | 200 | 127 / 73 | 16 | 16 | 166 | 5.61 | 616 / 316 | 25 |
| fullstack | 200 | 129 / 71 | 16 | 19 | 166 | 4.96 | 502 / 322 | 21 |
| data | 200 | 136 / 64 | 16 | 15 | 169 | 4.76 | 617 / 187 | 25 |

Row shape: `{job: Job, gold: {action, is_scam, has_injection, evidence_ids[], fair_price_band, requirements[], job_type, ...}}`.

- **Gold evidence** = up to 6 case-study / repo items whose true skills overlap the job's required
  skills most (`gigsim/generate.py: evidence_for`). Reviews, the CV and past proposals are never gold.
  Because jobs often have 6 gold items, the maximum achievable Recall@5 on such jobs is 5/6.
- Jobs without gold evidence (off-profile categories) are excluded from Recall/MRR/nDCG and used to
  measure refusal instead.
- **Requirements**: every dev job has at least 4 gold requirements (200/200 per persona), so the
  ">=4 vs <4 requirements" breakdown has an empty "<4" bucket; the eval also reports a breakdown by
  number of `skills_required` (>=4 vs <4).
- Scam and injection labels come from the generator's hidden fields; scam jobs can still have gold
  evidence (the skills match, the client is the problem).

## Known limitations

- Template-generated text: vocabulary is narrower and more regular than real portfolios; absolute
  metric values will not transfer to real users, comparisons between variants are what matter.
- Gold evidence is defined by skill overlap, which favours lexical / skill-aware retrieval.
- The dev set doubles as the calibration set for a few thresholds (see
  `evals/results/rag_hypothesis.md`); no hidden test set is in the repo.
