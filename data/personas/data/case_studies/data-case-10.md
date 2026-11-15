---
id: data-case-10
title: Inventory Planning Model
project: inventory-excel-model
skills:
- excel
- forecasting
date: 2024-08
client_industry: wholesale
outcome: paused
---

# Inventory Planning Model

In August 2024 I was asked to help a mid-sized wholesale company where buyers reordered from memory and ran out of best sellers.
I shared a short written plan in the first week so nobody was surprised by scope later. We started with a two-day discovery session to agree on what success would look like and how it would be measured. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## What I did

Duplicate customers were merged, broken dates repaired and free-text country names standardised. I used excel to hand the finance team a model they could edit. I used sales forecasting to project next quarter's revenue.

We fitted regressions with confidence intervals and checked residuals before telling anyone a driver mattered. Security review asked for audit logs on every action, so we added them early. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Results

The headline number: it reduced stock-outs by 57%. Most of the hard problems were about messy inputs rather than clever algorithms. We deliberately left out two features the client asked for at the start because they did not move the main metric. I wrote the documentation as I went instead of at the end, which made the handover painless. Handover included a recorded walkthrough and a short runbook for whoever is on call. The first version was deliberately boring, and that is why it shipped on time. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The wholesale team had strong opinions about edge cases, and most of them turned out to be right. Demos happened every Friday, which kept feedback small and frequent. The client's own staff can now extend it without me, which was an explicit goal. Data access took longer than the build itself; getting the right permissions was a project of its own.

## Stack

VLOOKUP, forecasting, plus the usual tooling.
