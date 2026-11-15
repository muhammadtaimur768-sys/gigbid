---
id: aiml-case-03
title: Contract Clause Extraction
project: contract-clause-extractor
skills:
- nlp
- huggingface transformers
date: 2023-07
client_industry: legal
outcome: delivered
---

# Contract Clause Extraction

This engagement started with a complaint from the operations lead: paralegals copied renewal dates and liability caps out of contracts by hand.
When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I wrote the documentation as I went instead of at the end, which made the handover painless. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## What I did

I used text classification to pull entities and intents out of free text. We wrote our own training loop with mixed precision and gradient accumulation to fit a single 24 GB card. I used transformers to start from a pretrained encoder.

Everything from the ingestion scripts to the training loop lived in one typed codebase with a small CLI. A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class. We deliberately left out two features the client asked for at the start because they did not move the main metric. Most of the hard problems were about messy inputs rather than clever algorithms.

## Results

The headline number: it reached 0.91 F1 on renewal and liability clauses. Data access took longer than the build itself; getting the right permissions was a project of its own. Handover included a recorded walkthrough and a short runbook for whoever is on call. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The first version was deliberately boring, and that is why it shipped on time. I shared a short written plan in the first week so nobody was surprised by scope later. We tracked a small set of numbers weekly and dropped anything nobody looked at. The client's own staff can now extend it without me, which was an explicit goal. Security review asked for audit logs on every action, so we added them early. Demos happened every Friday, which kept feedback small and frequent.

Code: github.com/aokafor-ml/clausewise
