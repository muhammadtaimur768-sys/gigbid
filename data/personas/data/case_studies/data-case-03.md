---
id: data-case-03
title: Pricing Experiment Analysis
project: pricing-ab-test
skills:
- a/b testing
- statistics
date: 2025-01
client_industry: consumer
outcome: handed over
---

# Pricing Experiment Analysis

The brief was simple to state and hard to do: the company changed prices on gut feeling, and the consumer business wanted that fixed.
We started with a two-day discovery session to agree on what success would look like and how it would be measured. The first version was deliberately boring, and that is why it shipped on time. The client's own staff can now extend it without me, which was an explicit goal.

## What I did

The monthly refresh became a notebook-turned-script that ran in a few minutes instead of a day. I used split testing to judge the pricing experiment. I used regression to separate signal from noise.

Most of the logic was set-based queries with window functions and common table expressions. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Results

Within the first quarter the system found a 14% revenue uplift at the higher tier. Demos happened every Friday, which kept feedback small and frequent. Security review asked for audit logs on every action, so we added them early. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Most of the hard problems were about messy inputs rather than clever algorithms. We tracked a small set of numbers weekly and dropped anything nobody looked at. Data access took longer than the build itself; getting the right permissions was a project of its own. I wrote the documentation as I went instead of at the end, which made the handover painless. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call. The consumer team had strong opinions about edge cases, and most of them turned out to be right.

Code: github.com/praman-data/price-lab
