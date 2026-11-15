---
id: data-case-04
title: GA4 Tracking Rebuild
project: ga4-migration
skills:
- google analytics
- looker studio
date: 2024-09
client_industry: media
outcome: delivered
---

# GA4 Tracking Rebuild

The brief was simple to state and hard to do: conversions disappeared after the analytics migration, and the media business wanted that fixed.
Data access took longer than the build itself; getting the right permissions was a project of its own. Security review asked for audit logs on every action, so we added them early. I wrote the documentation as I went instead of at the end, which made the handover painless.

## What I did

I used google analytics to fix the tracking plan. Most of the logic was set-based queries with window functions and common table expressions. Billions of event rows were queried in partitioned, clustered tables in the client's cloud project.

I used looker studio to share a free self-serve report. We tracked a small set of numbers weekly and dropped anything nobody looked at. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Results

Measured against the old process, it recovered 63% of untracked conversions. The media team had strong opinions about edge cases, and most of them turned out to be right. We deliberately left out two features the client asked for at the start because they did not move the main metric. The first version was deliberately boring, and that is why it shipped on time. The client's own staff can now extend it without me, which was an explicit goal. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Most of the hard problems were about messy inputs rather than clever algorithms. A pilot with one team came first; the wider rollout followed after two weeks of fixes. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call. Demos happened every Friday, which kept feedback small and frequent.

## Stack

GA4, looker studio, plus the usual tooling.
