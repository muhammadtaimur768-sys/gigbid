---
id: data-case-05
title: Hospital Operations Workbook
project: hospital-ops-tableau
skills:
- tableau
- sql
date: 2025-06
client_industry: healthcare
outcome: extended
---

# Hospital Operations Workbook

This engagement started with a complaint from the operations lead: bed managers phoned each ward for occupancy every morning.
We started with a two-day discovery session to agree on what success would look like and how it would be measured. We deliberately left out two features the client asked for at the start because they did not move the main metric. Data access took longer than the build itself; getting the right permissions was a project of its own.

## What I did

Each view answered one question, with the headline number top-left and the drill-downs underneath. I used sql to model and query the sales data. I used Tableau to publish the operations workbook.

A nightly job pulled the CRM, ERP and ad platforms into one place, with row counts checked at every step. A pilot with one team came first; the wider rollout followed after two weeks of fixes. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Results

Within the first quarter the system gave 12 ward managers a live view. The healthcare team had strong opinions about edge cases, and most of them turned out to be right. Most of the hard problems were about messy inputs rather than clever algorithms. I shared a short written plan in the first week so nobody was surprised by scope later. The client's own staff can now extend it without me, which was an explicit goal. I wrote the documentation as I went instead of at the end, which made the handover painless. Security review asked for audit logs on every action, so we added them early. We tracked a small set of numbers weekly and dropped anything nobody looked at. Handover included a recorded walkthrough and a short runbook for whoever is on call. The first version was deliberately boring, and that is why it shipped on time. Demos happened every Friday, which kept feedback small and frequent.

## Stack

Tableau, T-SQL, plus the usual tooling.
