---
id: aiml-case-16
title: Grid Load Forecasting
project: energy-load-forecast
skills:
- time series forecasting
- mlops
date: 2026-03
client_industry: energy
outcome: paused
---

# Grid Load Forecasting

A energy client came to me because the retailer bought peak power at spot prices because forecasts were off.
A pilot with one team came first; the wider rollout followed after two weeks of fixes. We tracked a small set of numbers weekly and dropped anything nobody looked at. Security review asked for audit logs on every action, so we added them early.

## What I did

I used ML ops to track experiments and monitor drift after launch. Everything from the ingestion scripts to the training loop lived in one typed codebase with a small CLI. Retraining, evaluation and promotion ran as a scheduled pipeline every night with retries and alerts.

I used time series forecasting to forecast weekly demand per store. The client's own staff can now extend it without me, which was an explicit goal. Most of the hard problems were about messy inputs rather than clever algorithms.

## Results

Within the first quarter the system cut forecast error by 40%. Data access took longer than the build itself; getting the right permissions was a project of its own. The energy team had strong opinions about edge cases, and most of them turned out to be right. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call. I wrote the documentation as I went instead of at the end, which made the handover painless. The first version was deliberately boring, and that is why it shipped on time. We deliberately left out two features the client asked for at the start because they did not move the main metric. We started with a two-day discovery session to agree on what success would look like and how it would be measured. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Demos happened every Friday, which kept feedback small and frequent.

## Stack

demand forecasting, ML ops, plus the usual tooling.
