---
id: aiml-case-02
title: Support Copilot for a SaaS Help Desk
project: support-copilot
skills:
- rag
- langchain
- vector databases
date: 2023-07
client_industry: saas
outcome: paused
---

# Support Copilot for a SaaS Help Desk

The brief was simple to state and hard to do: support agents searched three wikis for every answer and gave inconsistent replies, and the saas business wanted that fixed.
The saas team had strong opinions about edge cases, and most of them turned out to be right. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## What I did

The whole service shipped as one image the client's ops team could run with a single command. The model was served behind a typed HTTP endpoint with request validation and auto-generated docs. I used langchain to wire the prompts, retrievers and output parsers. I used rag to ground answers in the client's own documents.

I used vector databases to store and search the embeddings. We iterated on the instructions and few-shot examples until the outputs matched the client's template every time. The first version was deliberately boring, and that is why it shipped on time. The client's own staff can now extend it without me, which was an explicit goal.

## Results

The headline number: it deflected 25% of tier-1 tickets. We tracked a small set of numbers weekly and dropped anything nobody looked at. Data access took longer than the build itself; getting the right permissions was a project of its own. Handover included a recorded walkthrough and a short runbook for whoever is on call. Security review asked for audit logs on every action, so we added them early. I wrote the documentation as I went instead of at the end, which made the handover painless. Most of the hard problems were about messy inputs rather than clever algorithms. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I shared a short written plan in the first week so nobody was surprised by scope later. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## Stack

retrieval-augmented generation, LangChain, plus the usual tooling.
