---
id: data-case-02
title: Warehouse Rebuild in dbt and Snowflake
project: dbt-warehouse
skills:
- dbt
- snowflake
date: 2025-02
client_industry: ecommerce
outcome: extended
---

# Warehouse Rebuild in dbt and Snowflake

A ecommerce client came to me because every team had its own revenue number.
We tracked a small set of numbers weekly and dropped anything nobody looked at. The first version was deliberately boring, and that is why it shipped on time. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## What I did

Most of the logic was set-based queries with window functions and common table expressions. The refresh ran on a scheduler every morning before 7am and paged us if a source was late. A nightly job pulled the CRM, ERP and ad platforms into one place, with row counts checked at every step.

I used dbt to turn the raw tables into tested models. I used Snowflake to host the warehouse. The ecommerce team had strong opinions about edge cases, and most of them turned out to be right. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## Results

Within the first quarter the system replaced 25 conflicting revenue definitions with one. We deliberately left out two features the client asked for at the start because they did not move the main metric. Data access took longer than the build itself; getting the right permissions was a project of its own. Most of the hard problems were about messy inputs rather than clever algorithms. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Demos happened every Friday, which kept feedback small and frequent. I shared a short written plan in the first week so nobody was surprised by scope later. Security review asked for audit logs on every action, so we added them early. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The client's own staff can now extend it without me, which was an explicit goal. I wrote the documentation as I went instead of at the end, which made the handover painless.

Code: github.com/praman-data/lakehouse-lite
