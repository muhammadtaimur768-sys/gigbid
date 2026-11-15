---
id: data-case-09
title: Marketing Spend Dashboard
project: marketing-attribution
skills:
- looker studio
- bigquery
date: 2025-09
client_industry: travel
outcome: delivered
---

# Marketing Spend Dashboard

In September 2025 I was asked to help a mid-sized travel company where the agency could not say which channel drove bookings.
The travel team had strong opinions about edge cases, and most of them turned out to be right. Handover included a recorded walkthrough and a short runbook for whoever is on call. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## What I did

I used BigQuery to query the event exports at scale. Most of the logic was set-based queries with window functions and common table expressions. I used Data Studio to share a free self-serve report.

We rebuilt the site's tracking plan, events and conversion definitions after the migration broke them. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I shared a short written plan in the first week so nobody was surprised by scope later.

## Results

Within the first quarter the system reallocated 32% of spend to better channels. I wrote the documentation as I went instead of at the end, which made the handover painless. We tracked a small set of numbers weekly and dropped anything nobody looked at. We deliberately left out two features the client asked for at the start because they did not move the main metric. Security review asked for audit logs on every action, so we added them early. The client's own staff can now extend it without me, which was an explicit goal. Demos happened every Friday, which kept feedback small and frequent. The first version was deliberately boring, and that is why it shipped on time. Most of the hard problems were about messy inputs rather than clever algorithms. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Data access took longer than the build itself; getting the right permissions was a project of its own.
