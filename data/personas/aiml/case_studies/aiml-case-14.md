---
id: aiml-case-14
title: Real-Time Fraud Scoring API
project: fraud-scoring
skills:
- fastapi
- scikit-learn
date: 2026-02
client_industry: fintech
outcome: paused
---

# Real-Time Fraud Scoring API

This engagement started with a complaint from the operations lead: chargebacks were growing faster than revenue.
Demos happened every Friday, which kept feedback small and frequent. We tracked a small set of numbers weekly and dropped anything nobody looked at. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## What I did

Inference pods scaled horizontally on queue depth, with rolling deploys and no downtime. A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class. I used scikit-learn to build the classical baselines.

The whole service shipped as one image the client's ops team could run with a single command. I used fastapi to expose the model behind a typed HTTP API. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The fintech team had strong opinions about edge cases, and most of them turned out to be right.

## Results

Measured against the old process, it blocked 57% of fraudulent transactions. I shared a short written plan in the first week so nobody was surprised by scope later. A pilot with one team came first; the wider rollout followed after two weeks of fixes. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The first version was deliberately boring, and that is why it shipped on time. Security review asked for audit logs on every action, so we added them early. Data access took longer than the build itself; getting the right permissions was a project of its own. Handover included a recorded walkthrough and a short runbook for whoever is on call. Most of the hard problems were about messy inputs rather than clever algorithms. The client's own staff can now extend it without me, which was an explicit goal. I wrote the documentation as I went instead of at the end, which made the handover painless.
