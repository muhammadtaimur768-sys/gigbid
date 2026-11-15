---
id: data-case-01
title: Executive Sales Dashboard
project: exec-sales-dashboard
skills:
- power bi
- sql
date: 2022-11
client_industry: retail
outcome: paused
---

# Executive Sales Dashboard

This engagement started with a complaint from the operations lead: the leadership pack took two analysts four days each month.
Demos happened every Friday, which kept feedback small and frequent. We tracked a small set of numbers weekly and dropped anything nobody looked at. The retail team had strong opinions about edge cases, and most of them turned out to be right.

## What I did

Duplicate customers were merged, broken dates repaired and free-text country names standardised. Each view answered one question, with the headline number top-left and the drill-downs underneath. I used sql to model and query the sales data.

I used Power BI to build the executive report. Finance received a workbook with lookups, pivot tables and a protected assumptions tab they could edit themselves. Security review asked for audit logs on every action, so we added them early. I wrote the documentation as I went instead of at the end, which made the handover painless.

## Results

The headline number: it cut reporting time from four days to 23 hours. The first version was deliberately boring, and that is why it shipped on time. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We deliberately left out two features the client asked for at the start because they did not move the main metric. Most of the hard problems were about messy inputs rather than clever algorithms. We started with a two-day discovery session to agree on what success would look like and how it would be measured. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The client's own staff can now extend it without me, which was an explicit goal. Handover included a recorded walkthrough and a short runbook for whoever is on call. I shared a short written plan in the first week so nobody was surprised by scope later. Data access took longer than the build itself; getting the right permissions was a project of its own.

## Stack

DAX, sql, plus the usual tooling.
