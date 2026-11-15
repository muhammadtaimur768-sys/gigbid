---
id: data-case-12
title: Subscriber Churn Analysis
project: churn-analysis
skills:
- statistics
- sql
date: 2024-03
client_industry: fitness
outcome: handed over
---

# Subscriber Churn Analysis

In March 2024 I was asked to help a mid-sized fitness company where the gym chain did not know why members cancelled.
The client's own staff can now extend it without me, which was an explicit goal. Security review asked for audit logs on every action, so we added them early. Data access took longer than the build itself; getting the right permissions was a project of its own.

## What I did

The monthly refresh became a notebook-turned-script that ran in a few minutes instead of a day. I used sql to model and query the sales data. I used statistics to separate signal from noise.

Exports from three systems were reshaped, merged on customer keys and pivoted in memory. Each view answered one question, with the headline number top-left and the drill-downs underneath. I wrote the documentation as I went instead of at the end, which made the handover painless. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## Results

The headline number: it found the 15 strongest churn signals. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The first version was deliberately boring, and that is why it shipped on time. Handover included a recorded walkthrough and a short runbook for whoever is on call. The fitness team had strong opinions about edge cases, and most of them turned out to be right. Most of the hard problems were about messy inputs rather than clever algorithms. We deliberately left out two features the client asked for at the start because they did not move the main metric. We started with a two-day discovery session to agree on what success would look like and how it would be measured. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I shared a short written plan in the first week so nobody was surprised by scope later. Demos happened every Friday, which kept feedback small and frequent.

## Stack

statistics, sql, plus the usual tooling.
