---
id: aiml-case-07
title: KYC Review Agent with Human Approval
project: kyc-agent
skills:
- langgraph
- langchain
date: 2026-07
client_industry: fintech
outcome: extended
---

# KYC Review Agent with Human Approval

The brief was simple to state and hard to do: compliance analysts re-keyed data from ID documents into three systems, and the fintech business wanted that fixed.
I wrote the documentation as I went instead of at the end, which made the handover painless. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Demos happened every Friday, which kept feedback small and frequent.

## What I did

I used langgraph to orchestrate the multi-step agent with human approval. Everything from the ingestion scripts to the training loop lived in one typed codebase with a small CLI. I used langchain to wire the prompts, retrievers and output parsers.

We iterated on the instructions and few-shot examples until the outputs matched the client's template every time. The model was served behind a typed HTTP endpoint with request validation and auto-generated docs. We started with a two-day discovery session to agree on what success would look like and how it would be measured. I shared a short written plan in the first week so nobody was surprised by scope later.

## Results

The headline number: it halved review time per applicant. The first version was deliberately boring, and that is why it shipped on time. The fintech team had strong opinions about edge cases, and most of them turned out to be right. Security review asked for audit logs on every action, so we added them early. The client's own staff can now extend it without me, which was an explicit goal. Data access took longer than the build itself; getting the right permissions was a project of its own. Most of the hard problems were about messy inputs rather than clever algorithms. We tracked a small set of numbers weekly and dropped anything nobody looked at. Handover included a recorded walkthrough and a short runbook for whoever is on call. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Stack

agent graphs, LangChain, plus the usual tooling.

Code: github.com/aokafor-ml/kyc-graph
