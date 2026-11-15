---
id: aiml-case-11
title: Semantic Product Search
project: product-search-embeddings
skills:
- vector databases
- huggingface transformers
date: 2024-05
client_industry: ecommerce
outcome: delivered
---

# Semantic Product Search

The brief was simple to state and hard to do: shoppers searching in plain language got zero results, and the ecommerce business wanted that fixed.
The client's own staff can now extend it without me, which was an explicit goal. The first version was deliberately boring, and that is why it shipped on time. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## What I did

The model was served behind a typed HTTP endpoint with request validation and auto-generated docs. Everything from the ingestion scripts to the training loop lived in one typed codebase with a small CLI. A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class.

I used Qdrant to store and search the embeddings. I used huggingface transformers to start from a pretrained encoder. Data access took longer than the build itself; getting the right permissions was a project of its own. I shared a short written plan in the first week so nobody was surprised by scope later.

## Results

Within the first quarter the system raised search conversion by 43%. I wrote the documentation as I went instead of at the end, which made the handover painless. We tracked a small set of numbers weekly and dropped anything nobody looked at. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Most of the hard problems were about messy inputs rather than clever algorithms. Demos happened every Friday, which kept feedback small and frequent. Security review asked for audit logs on every action, so we added them early. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Handover included a recorded walkthrough and a short runbook for whoever is on call. The ecommerce team had strong opinions about edge cases, and most of them turned out to be right. We deliberately left out two features the client asked for at the start because they did not move the main metric.
