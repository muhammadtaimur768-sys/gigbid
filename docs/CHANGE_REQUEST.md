# Change request: platform policy update 2026-11-02

## The request

The marketplace announced two rule changes, effective 2026-11-02:

1. **Early-bird Connects surcharge.** Bidding on a job posted less than 1 hour ago costs +2 Connects.
2. **Proposal length limit.** A cover letter must not exceed 2,500 characters. Longer proposals are
   rejected by the platform (HTTP 422 `proposal_too_long`).

## How it was absorbed: config only, no code change

The update ships as a data file, `data/policy_pack/updates/2026-11-02.yaml`. The agent merges every file in
`data/policy_pack/updates/` into `data/policy_pack/rules.yaml` once its `effective` date has passed
(`agent/settings.py: load_policy()`). Rules, actions and limits are read from the merged policy at run time.

| Change | Where the agent reads it | Effect |
|---|---|---|
| Early-bird surcharge (`changes[].type: connects_surcharge`, `bidding_overrides.early_bird_surcharge`) | `agent/policy.py: connects_cost()` (Pricing Strategist, PriceQuote.connects_cost) | The quote and the `worth_connects` check include the surcharge. The dry-run preview from the marketplace shows the cost it will actually charge. |
| Length limit (`changes[].type: new_rule`, `max_chars: 2500`, `bidding_overrides.max_proposal_chars`) | `agent/settings.py: max_proposal_chars()`, `agent/policy.py: check_outbound()` | The Compliance Guard blocks a draft or user edit over the limit, with the reason `max_proposal_length` (shown in the UI), and the Critic asks for a shorter letter. The Writer's own cap (`agent/config.yaml: writer.max_chars: 2400`) stays below the limit. |

Before the effective date the update is ignored. Set `GIGBID_TODAY=2026-10-01` to replay the old policy.

## Verification

- `tests/unit/test_agent_units.py::test_policy_update_absorbed_from_config`: the update is applied and
  the limit is 2,500.
- `test_policy_update_not_applied_before_effective_date`: the update is not applied before 2026-11-02.
- `test_early_bird_surcharge`: 6 → 8 Connects for a job posted 20 minutes ago, still 6 for one posted 5 hours ago.
- `test_outbound_compliance_block_and_redact`: a 2,600-character letter is blocked as `max_proposal_length`.

## How to absorb the next change

Add `data/policy_pack/updates/<date>.yaml` with an `effective` date and either `changes` entries
(`new_rule` / `update_rule` with `id, description, kind: regex|llm, patterns, action: block|redact`, or
`connects_surcharge`) or `bidding_overrides`. You only need to touch code for a new kind of condition the
policy loader does not understand yet, such as a surcharge keyed on a new job field.
