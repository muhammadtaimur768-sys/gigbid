---
id: data-case-08
title: Quarterly Revenue Forecast
project: revenue-forecast
skills:
- forecasting
- python
date: 2023-03
client_industry: saas
outcome: handed over
---

# Quarterly Revenue Forecast

A saas client came to me because finance missed its quarterly forecast three times in a row.
Most of the hard problems were about messy inputs rather than clever algorithms. The client's own staff can now extend it without me, which was an explicit goal. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## What I did

I used Python to automate the monthly refresh. Exports from three systems were reshaped, merged on customer keys and pivoted in memory. I used forecasting to project next quarter's revenue.

Finance received a workbook with lookups, pivot tables and a protected assumptions tab they could edit themselves. We fitted regressions with confidence intervals and checked residuals before telling anyone a driver mattered. Security review asked for audit logs on every action, so we added them early. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## Results

Measured against the old process, it brought forecast error under 23%. The first version was deliberately boring, and that is why it shipped on time. We deliberately left out two features the client asked for at the start because they did not move the main metric. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. A pilot with one team came first; the wider rollout followed after two weeks of fixes. I wrote the documentation as I went instead of at the end, which made the handover painless. I shared a short written plan in the first week so nobody was surprised by scope later. The saas team had strong opinions about edge cases, and most of them turned out to be right. Handover included a recorded walkthrough and a short runbook for whoever is on call. Demos happened every Friday, which kept feedback small and frequent. Data access took longer than the build itself; getting the right permissions was a project of its own.

## Stack

time series, Jupyter, plus the usual tooling.

Code: github.com/praman-data/forecastly
