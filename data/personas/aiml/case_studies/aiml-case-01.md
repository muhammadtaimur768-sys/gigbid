---
id: aiml-case-01
title: Claims Triage Assistant
project: claims-triage-assistant
skills:
- rag
- python
date: 2025-02
client_industry: insurance
outcome: delivered
---

# Claims Triage Assistant

In February 2025 I was asked to help a mid-sized insurance company where adjusters spent the first hour of every claim reading PDFs to decide who should handle it.
The first version was deliberately boring, and that is why it shipped on time. The insurance team had strong opinions about edge cases, and most of them turned out to be right. Data access took longer than the build itself; getting the right permissions was a project of its own.

## What I did

We iterated on the instructions and few-shot examples until the outputs matched the client's template every time. I used REST API to expose the model behind a typed HTTP API. I used python to glue the data pipeline and model code together. I used rag to ground answers in the client's own documents.

Embeddings sat in a nearest-neighbour index with metadata filters by product line and date. A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class. Security review asked for audit logs on every action, so we added them early. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Results

The headline number: it cut first-touch time by 29%. We started with a two-day discovery session to agree on what success would look like and how it would be measured. I shared a short written plan in the first week so nobody was surprised by scope later. I wrote the documentation as I went instead of at the end, which made the handover painless. Demos happened every Friday, which kept feedback small and frequent. Most of the hard problems were about messy inputs rather than clever algorithms. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Handover included a recorded walkthrough and a short runbook for whoever is on call. We tracked a small set of numbers weekly and dropped anything nobody looked at.

Code: github.com/aokafor-ml/doc-sieve
