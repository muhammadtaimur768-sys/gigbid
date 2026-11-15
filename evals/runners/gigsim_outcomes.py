"""GigSim outcome eval: reply / interview / hire rate of the agent's proposals under GigSim's client model,
compared with a generic template baseline on the same jobs.

Reads evals/results/decision_records_<config>.jsonl written by decision_eval.

    python -m evals.runners.gigsim_outcomes --config heuristic
"""
from __future__ import annotations

import argparse
import json

from agent.prompts import load_prompt
from evals.runners.agent_harness import RESULTS, score_outcomes, write_json


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="*", default=None)
    args = ap.parse_args(argv)
    configs = args.configs or sorted(p.stem.replace("decision_records_", "") for p in RESULTS.glob("decision_records_*.jsonl"))
    template, _ = load_prompt("baseline_generic")
    out = {}
    for c in configs:
        recs = [json.loads(line) for line in open(RESULTS / f"decision_records_{c}.jsonl")]
        agent_sum, _ = score_outcomes(recs)
        base = []
        for r in recs:
            if r.get("cover_letter"):
                skills = ", ".join(r["gold"].get("requirements", [])[:2])
                base.append({**r, "cover_letter": template.replace("$skills", skills or "this work")})
        base_sum, _ = score_outcomes(base)
        out[c] = {"agent": agent_sum, "generic_template_baseline": base_sum}
    write_json("gigsim_outcomes.json", out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
