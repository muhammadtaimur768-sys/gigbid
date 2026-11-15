---
id: aiml-case-17
title: HR Policy Assistant
project: hr-policy-chatbot
skills:
- rag
- prompt engineering
date: 2023-07
client_industry: manufacturing
outcome: extended
---

# HR Policy Assistant

A manufacturing client came to me because HR answered the same leave and benefits questions hundreds of times a month.
Demos happened every Friday, which kept feedback small and frequent. Security review asked for audit logs on every action, so we added them early. Most of the hard problems were about messy inputs rather than clever algorithms.

## What I did

I used rag to ground answers in the client's own documents. Embeddings sat in a nearest-neighbour index with metadata filters by product line and date. Prompt templates, retrievers and output parsers were composed as small runnable pipelines.

Training ran on rented GPU instances in the client's cloud account and the endpoint scaled to zero at night. I used prompt engineering to make the model follow the client's format reliably. I shared a short written plan in the first week so nobody was surprised by scope later. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Results

Measured against the old process, it answered 40% of HR questions without escalation. Data access took longer than the build itself; getting the right permissions was a project of its own. The manufacturing team had strong opinions about edge cases, and most of them turned out to be right. We tracked a small set of numbers weekly and dropped anything nobody looked at. I wrote the documentation as I went instead of at the end, which made the handover painless. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We started with a two-day discovery session to agree on what success would look like and how it would be measured. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The client's own staff can now extend it without me, which was an explicit goal. Handover included a recorded walkthrough and a short runbook for whoever is on call. The first version was deliberately boring, and that is why it shipped on time.

## Stack

retrieval augmented generation, prompt design, plus the usual tooling.
