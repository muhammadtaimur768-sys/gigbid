---
id: data-case-16
title: E-Commerce Funnel Analysis
project: ecommerce-funnel
skills:
- google analytics
- sql
date: 2025-07
client_industry: ecommerce
outcome: delivered
---

# E-Commerce Funnel Analysis

This engagement started with a complaint from the operations lead: the shop had high traffic but few completed checkouts.
We deliberately left out two features the client asked for at the start because they did not move the main metric. Demos happened every Friday, which kept feedback small and frequent. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## What I did

I used sql to model and query the sales data. I used google analytics to fix the tracking plan. Billions of event rows were queried in partitioned, clustered tables in the client's cloud project.

Each view answered one question, with the headline number top-left and the drill-downs underneath. We sized the experiment up front, checked the split was balanced and only read the result at the planned sample size. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The first version was deliberately boring, and that is why it shipped on time.

## Results

Measured against the old process, it lifted checkout completion by 46%. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The client's own staff can now extend it without me, which was an explicit goal. Data access took longer than the build itself; getting the right permissions was a project of its own. Security review asked for audit logs on every action, so we added them early. I wrote the documentation as I went instead of at the end, which made the handover painless. The ecommerce team had strong opinions about edge cases, and most of them turned out to be right. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call. Most of the hard problems were about messy inputs rather than clever algorithms.
