---
id: fullstack-case-11
title: Internal CRM Dashboard
project: crm-dashboard
skills:
- react
- express
date: 2023-02
client_industry: energy
outcome: delivered
---

# Internal CRM Dashboard

This engagement started with a complaint from the operations lead: sales managers had no live view of the pipeline.
Most of the hard problems were about messy inputs rather than clever algorithms. Security review asked for audit logs on every action, so we added them early. I shared a short written plan in the first week so nobody was surprised by scope later.

## What I did

I used PostgreSQL to store orders and users relationally. I used express to define the REST routes and middleware. Users signed in with their existing Google or Microsoft accounts and tokens were refreshed silently.

Sessions, rate-limit counters and hot queries sat in an in-memory key-value store in front of the database. I used react to build the component library and screens. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Results

The headline number: it gave 18 managers a live pipeline view. I wrote the documentation as I went instead of at the end, which made the handover painless. Demos happened every Friday, which kept feedback small and frequent. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We tracked a small set of numbers weekly and dropped anything nobody looked at. The first version was deliberately boring, and that is why it shipped on time. The energy team had strong opinions about edge cases, and most of them turned out to be right. The client's own staff can now extend it without me, which was an explicit goal. Handover included a recorded walkthrough and a short runbook for whoever is on call. Data access took longer than the build itself; getting the right permissions was a project of its own. We started with a two-day discovery session to agree on what success would look like and how it would be measured.
