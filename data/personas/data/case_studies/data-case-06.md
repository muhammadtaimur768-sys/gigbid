---
id: data-case-06
title: Customer Satisfaction Survey Study
project: customer-survey
skills:
- survey analysis
- r
date: 2025-04
client_industry: telecom
outcome: extended
---

# Customer Satisfaction Survey Study

This engagement started with a complaint from the operations lead: the telecom collected surveys but never analysed the open answers.
The telecom team had strong opinions about edge cases, and most of them turned out to be right. Security review asked for audit logs on every action, so we added them early. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## What I did

We fitted regressions with confidence intervals and checked residuals before telling anyone a driver mattered. Duplicate customers were merged, broken dates repaired and free-text country names standardised. I used survey analysis to analyse the customer survey.

I used R to run the survey models and charts. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Most of the hard problems were about messy inputs rather than clever algorithms.

## Results

Measured against the old process, it identified the 28 drivers behind detractor scores. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The client's own staff can now extend it without me, which was an explicit goal. Data access took longer than the build itself; getting the right permissions was a project of its own. I wrote the documentation as I went instead of at the end, which made the handover painless. We deliberately left out two features the client asked for at the start because they did not move the main metric. We tracked a small set of numbers weekly and dropped anything nobody looked at. The first version was deliberately boring, and that is why it shipped on time.

## Stack

survey data, R, plus the usual tooling.
