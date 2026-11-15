---
id: aiml-case-05
title: Store-Level Demand Forecasting
project: retail-demand-forecast
skills:
- time series forecasting
- python
date: 2024-10
client_industry: retail
outcome: delivered
---

# Store-Level Demand Forecasting

In October 2024 I was asked to help a mid-sized retail company where stores over-ordered fresh produce and threw away a tenth of it.
The first version was deliberately boring, and that is why it shipped on time. We deliberately left out two features the client asked for at the start because they did not move the main metric. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## What I did

Before any deep model we fitted gradient-boosted trees and logistic regression baselines with cross-validation. Retraining, evaluation and promotion ran as a scheduled pipeline every night with retries and alerts. I used forecasting to forecast weekly demand per store.

Training ran on rented GPU instances in the client's cloud account and the endpoint scaled to zero at night. I used py to glue the data pipeline and model code together. Handover included a recorded walkthrough and a short runbook for whoever is on call. I wrote the documentation as I went instead of at the end, which made the handover painless.

## Results

Within the first quarter the system reduced waste by 39%. We tracked a small set of numbers weekly and dropped anything nobody looked at. We started with a two-day discovery session to agree on what success would look like and how it would be measured. I shared a short written plan in the first week so nobody was surprised by scope later. Most of the hard problems were about messy inputs rather than clever algorithms. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The client's own staff can now extend it without me, which was an explicit goal. The retail team had strong opinions about edge cases, and most of them turned out to be right. Data access took longer than the build itself; getting the right permissions was a project of its own. Security review asked for audit logs on every action, so we added them early.
