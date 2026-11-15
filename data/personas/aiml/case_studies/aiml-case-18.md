---
id: aiml-case-18
title: LLM Evaluation Harness
project: eval-harness
skills:
- model evaluation
- python
date: 2023-01
client_industry: saas
outcome: extended
---

# LLM Evaluation Harness

This engagement started with a complaint from the operations lead: every prompt change was judged by vibes and regressions reached customers.
Security review asked for audit logs on every action, so we added them early. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## What I did

I used python to glue the data pipeline and model code together. We iterated on the instructions and few-shot examples until the outputs matched the client's template every time. I used evaluation to prove the model beat the baseline.

Prompt templates, retrievers and output parsers were composed as small runnable pipelines. The saas team had strong opinions about edge cases, and most of them turned out to be right. Demos happened every Friday, which kept feedback small and frequent.

## Results

Within the first quarter the system caught 3 regressions before release. The client's own staff can now extend it without me, which was an explicit goal. The first version was deliberately boring, and that is why it shipped on time. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Data access took longer than the build itself; getting the right permissions was a project of its own. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Most of the hard problems were about messy inputs rather than clever algorithms. I shared a short written plan in the first week so nobody was surprised by scope later. We deliberately left out two features the client asked for at the start because they did not move the main metric. I wrote the documentation as I went instead of at the end, which made the handover painless. We tracked a small set of numbers weekly and dropped anything nobody looked at.

Code: github.com/aokafor-ml/evalkit
