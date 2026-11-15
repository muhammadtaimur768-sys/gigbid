---
id: data-case-13
title: Finance KPI Pack
project: finance-kpi-powerbi
skills:
- power bi
- excel
date: 2022-12
client_industry: construction
outcome: paused
---

# Finance KPI Pack

In December 2022 I was asked to help a mid-sized construction company where project margins were only known after projects closed.
We deliberately left out two features the client asked for at the start because they did not move the main metric. Demos happened every Friday, which kept feedback small and frequent. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## What I did

Most of the logic was set-based queries with window functions and common table expressions. Each view answered one question, with the headline number top-left and the drill-downs underneath. I used Power BI to build the executive report.

I used pivot tables to hand the finance team a model they could edit. Security review asked for audit logs on every action, so we added them early. The construction team had strong opinions about edge cases, and most of them turned out to be right.

## Results

Measured against the old process, it flagged 18 loss-making projects early. The client's own staff can now extend it without me, which was an explicit goal. Most of the hard problems were about messy inputs rather than clever algorithms. Handover included a recorded walkthrough and a short runbook for whoever is on call. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I shared a short written plan in the first week so nobody was surprised by scope later. I wrote the documentation as I went instead of at the end, which made the handover painless. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The first version was deliberately boring, and that is why it shipped on time. Data access took longer than the build itself; getting the right permissions was a project of its own. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## Stack

DAX, VLOOKUP, plus the usual tooling.
