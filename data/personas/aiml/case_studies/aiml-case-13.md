---
id: aiml-case-13
title: Sales Research Agent
project: sales-email-agent
skills:
- langgraph
- prompt engineering
date: 2026-03
client_industry: saas
outcome: delivered
---

# Sales Research Agent

The brief was simple to state and hard to do: reps spent an hour researching each prospect before a call, and the saas business wanted that fixed.
Security review asked for audit logs on every action, so we added them early. We deliberately left out two features the client asked for at the start because they did not move the main metric. Demos happened every Friday, which kept feedback small and frequent.

## What I did

Answers were only produced from passages pulled out of the client's manuals, and every answer cited the page it came from. The model was served behind a typed HTTP endpoint with request validation and auto-generated docs. I used agent graphs to orchestrate the multi-step agent with human approval.

I used prompt design to make the model follow the client's format reliably. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## Results

Measured against the old process, it saved 22 hours a week across the team. Handover included a recorded walkthrough and a short runbook for whoever is on call. I shared a short written plan in the first week so nobody was surprised by scope later. Data access took longer than the build itself; getting the right permissions was a project of its own. We tracked a small set of numbers weekly and dropped anything nobody looked at. The saas team had strong opinions about edge cases, and most of them turned out to be right. The client's own staff can now extend it without me, which was an explicit goal. The first version was deliberately boring, and that is why it shipped on time. Most of the hard problems were about messy inputs rather than clever algorithms. I wrote the documentation as I went instead of at the end, which made the handover painless. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## Stack

agent graphs, prompt engineering, plus the usual tooling.
