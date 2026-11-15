"""Render the 30 judge-calibration proposals into a readable, blind labelling sheet.

Reads evals/results/judge_proposals.jsonl and writes evals/datasets/labeling_sheet.md.
Judge scores are deliberately NOT shown, so the human labels stay independent.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evals" / "results" / "judge_proposals.jsonl"
OUT = ROOT / "evals" / "datasets" / "labeling_sheet.md"

RUBRIC = """\
## Rubric (score 0-10, then pass or revise)

Score each proposal on four things, roughly equally weighted:

1. **Fit**: does it address the job's must-have requirements listed above it?
2. **Evidence**: are claims specific and backed by concrete past work (project, numbers), not vague?
3. **Personalisation**: does the opening speak to *this* client's problem, not a generic "Dear Sir / I am passionate"?
4. **Clarity and length**: easy to read, no padding, a clear next step.

**Verdict**: `pass` = you would send it as is (score about 7 or more); `revise` = it needs changes before sending.
"""


def main() -> None:
    rows = [json.loads(line) for line in SRC.read_text().splitlines() if line.strip()]
    parts = ["# Judge calibration: labelling sheet\n",
             "Fill in `evals/datasets/human_labels.csv` (one row per proposal id below).\n", RUBRIC]
    for r in rows:
        job = r["job"]
        budget = f"{job.get('budget_type')} {job.get('budget_min')}-{job.get('budget_max')}"
        reqs = "\n".join(f"- {t}" for t in r.get("requirements", []))
        answers = "\n".join(f"- **Q:** {a.get('question')}\n  **A:** {a.get('answer')}"
                            for a in (r.get("screening_answers") or []))
        parts.append(
            f"\n---\n\n## {r['proposal_id']} · {job.get('title')}\n\n"
            f"*Persona:* {r.get('persona')} · *Budget:* {budget} · *Job id:* {r['job_id']}\n\n"
            f"**Requirements**\n{reqs}\n\n**Cover letter**\n\n{r['cover_letter']}\n\n"
            + (f"**Screening answers**\n{answers}\n" if answers else "")
        )
    OUT.write_text("\n".join(parts))
    print(f"wrote {OUT} ({len(rows)} proposals)")


if __name__ == "__main__":
    main()
