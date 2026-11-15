# Signature extension: X2 Proposal experiments

GigBid can run two proposal strategies against each other as an A/B test in GigSim and decide
with a significance test whether one gets more replies. The same harness is meant for later
questions, for example "does leading with the client's problem beat leading with credentials?"

All results for this extension come from `evals/results/ab_experiment.json`, written by the
experiment runner. No number appears on this page. Read them from that file, or from the README
table generated from it.

## Question
Does strategy B get a higher simulated reply rate than strategy A on the same jobs, at the same
price, with the same evidence?

## Strategies
A strategy is a named configuration of the Proposal Writer, never a code fork:

| | Strategy A (control) | Strategy B (treatment) |
|---|---|---|
| Opening | evidence-first: the most relevant proven result in sentence one | problem-first: restates the client's core problem and the first deliverable |
| Structure | the shipped writer prompt | same, with the opening and paragraph order changed |
| Evidence, price, compliance | identical | identical |

Each strategy is a versioned prompt in `agent/prompts/` plus a `strategy` key in config, so the
experiment changes one variable. Claim verification, the Critic and the Compliance Guard run
unchanged on both arms. A strategy that only wins by making unsupported claims cannot win.

## Method
1. **Fixed job set.** Bid-eligible jobs from the GigSim stream (gold `bid` jobs in
   `evals/datasets/dev_*.jsonl`, across all three personas). Scams and injected posts are excluded,
   because the decision layer already skips them.
2. **Assignment.** Each job gets both arms (paired design). That removes job difficulty as a
   confounder. GigSim's simulated client scores each proposal independently through
   `gigsim.client_model.score_proposal`, so one arm cannot affect the other's outcome.
3. **Outcome.** The primary metric is reply rate (replied, interview or hired, divided by proposals).
   Secondary metrics are hire rate, unsupported claims per proposal and proposal length.
4. **Determinism.** GigSim runs with `GIGSIM_ERROR_RATE=0` and its seeded noise, and the writer runs
   at a fixed temperature and profile recorded in the results file. A rerun with the same seed
   reproduces the file.
5. **Significance test.** Paired binary outcomes, so the primary test is **McNemar's exact test** on
   the discordant pairs (A replied and B did not, and the reverse). A two-proportion z-test is
   reported alongside for readers who expect it. Significance level α = 0.05, two-sided, decided
   before the run. The results file reports the effect size (difference in reply rate) with a 95%
   bootstrap confidence interval, so a non-significant result still shows how large an effect the
   data rules out.
6. **Breakdown.** By persona and by job type, to find where a strategy helps and where it hurts.
   These are exploratory and not corrected for multiple comparisons. The results file labels them
   as such.
7. **Stopping rule.** Sample size is fixed in advance by the job set. No peeking and no early
   stopping.

## Running it
```bash
python -m evals.runners.ab_experiment          # writes evals/results/ab_experiment.json
```
The results file records the strategies (prompt versions), job ids, per-job outcomes for both
arms, the counts behind the test, the test statistics, p-values, the confidence interval, the
profile and the seed.

## How it surfaces in the product
- Analytics shows reply rate by strategy, from outcome events.
- Outcome memory (`("outcome", user_id, category)`) only promotes a strategy preference from real
  GigSim outcome events that meet the promotion rule in `agent/config.yaml`. It never promotes from
  the experiment's own claims.

## Results
See `evals/results/ab_experiment.json`. The decision on whether to switch the default strategy is
recorded in the R&D report, citing that file.

## Threats to validity
- GigSim's client model is deterministic scoring plus seeded noise. A strategy can learn to please
  the simulator, for example by mentioning must-have skills, without pleasing real clients. A
  simulator win is evidence only for the simulator.
- With a paired design and a modest job set, small effects are hard to detect. The confidence
  interval shows how large an effect the data can rule out.
- Hidden client preferences (e.g. "dislikes generic openings") interact with the opening style, so
  part of any effect may be specific to how GigSim models those preferences.
