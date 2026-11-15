---
id: aiml-case-10
title: MLOps Platform Migration
project: mlops-platform
skills:
- mlops
- kubernetes
date: 2025-07
client_industry: logistics
outcome: delivered
---

# MLOps Platform Migration

This engagement started with a complaint from the operations lead: models were retrained by hand on a laptop and nobody knew which version was live.
When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Most of the hard problems were about messy inputs rather than clever algorithms.

## What I did

Training ran on rented GPU instances in the client's cloud account and the endpoint scaled to zero at night. Retraining, evaluation and promotion ran as a scheduled pipeline every night with retries and alerts. I used k8s to run the inference fleet with autoscaling.

I used model monitoring to track experiments and monitor drift after launch. I used docker to package the service for the client's infrastructure. Security review asked for audit logs on every action, so we added them early. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## Results

Measured against the old process, it moved 31 models to automated retraining. I shared a short written plan in the first week so nobody was surprised by scope later. I wrote the documentation as I went instead of at the end, which made the handover painless. Handover included a recorded walkthrough and a short runbook for whoever is on call. The logistics team had strong opinions about edge cases, and most of them turned out to be right. The first version was deliberately boring, and that is why it shipped on time. Demos happened every Friday, which kept feedback small and frequent. The client's own staff can now extend it without me, which was an explicit goal. Data access took longer than the build itself; getting the right permissions was a project of its own. We tracked a small set of numbers weekly and dropped anything nobody looked at. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Stack

MLflow, EKS, plus the usual tooling.

Code: github.com/aokafor-ml/model-hangar
