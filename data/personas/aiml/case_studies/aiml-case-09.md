---
id: aiml-case-09
title: Subscriber Churn Prediction
project: churn-model
skills:
- scikit-learn
- python
date: 2022-12
client_industry: media
outcome: delivered
---

# Subscriber Churn Prediction

In December 2022 I was asked to help a mid-sized media company where the retention team contacted the wrong customers.
Demos happened every Friday, which kept feedback small and frequent. We deliberately left out two features the client asked for at the start because they did not move the main metric. I shared a short written plan in the first week so nobody was surprised by scope later.

## What I did

I used py to glue the data pipeline and model code together. A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class. Retraining, evaluation and promotion ran as a scheduled pipeline every night with retries and alerts.

I used sklearn to build the classical baselines. Data access took longer than the build itself; getting the right permissions was a project of its own. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## Results

Within the first quarter the system improved campaign lift by 18%. The client's own staff can now extend it without me, which was an explicit goal. I wrote the documentation as I went instead of at the end, which made the handover painless. Security review asked for audit logs on every action, so we added them early. We tracked a small set of numbers weekly and dropped anything nobody looked at. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The first version was deliberately boring, and that is why it shipped on time. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Most of the hard problems were about messy inputs rather than clever algorithms. The media team had strong opinions about edge cases, and most of them turned out to be right.
