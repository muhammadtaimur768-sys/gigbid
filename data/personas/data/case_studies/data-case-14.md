---
id: data-case-14
title: Supplier Lead-Time Analysis
project: supply-chain-sql
skills:
- sql
- pandas
date: 2026-05
client_industry: manufacturing
outcome: delivered
---

# Supplier Lead-Time Analysis

This engagement started with a complaint from the operations lead: late suppliers were discovered only when the line stopped.
A pilot with one team came first; the wider rollout followed after two weeks of fixes. The manufacturing team had strong opinions about edge cases, and most of them turned out to be right. I wrote the documentation as I went instead of at the end, which made the handover painless.

## What I did

I used Pandas to reshape and join the exports. I used sql to model and query the sales data. The operations team browsed a published workbook with parameter controls and level-of-detail calculations.

We fitted regressions with confidence intervals and checked residuals before telling anyone a driver mattered. We deliberately left out two features the client asked for at the start because they did not move the main metric. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Results

The headline number: it cut late deliveries by 31%. Handover included a recorded walkthrough and a short runbook for whoever is on call. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The client's own staff can now extend it without me, which was an explicit goal. We tracked a small set of numbers weekly and dropped anything nobody looked at. Data access took longer than the build itself; getting the right permissions was a project of its own. Demos happened every Friday, which kept feedback small and frequent. The first version was deliberately boring, and that is why it shipped on time. Most of the hard problems were about messy inputs rather than clever algorithms. Security review asked for audit logs on every action, so we added them early. I shared a short written plan in the first week so nobody was surprised by scope later.

## Stack

sql, dataframes, plus the usual tooling.
