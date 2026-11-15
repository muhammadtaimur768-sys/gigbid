---
id: data-case-11
title: Nightly CRM-to-Warehouse Pipeline
project: etl-pipeline
skills:
- etl
- airflow
date: 2025-05
client_industry: insurance
outcome: delivered
---

# Nightly CRM-to-Warehouse Pipeline

This engagement started with a complaint from the operations lead: reports used week-old CSV exports.
Most of the hard problems were about messy inputs rather than clever algorithms. Security review asked for audit logs on every action, so we added them early. The client's own staff can now extend it without me, which was an explicit goal.

## What I did

The monthly refresh became a notebook-turned-script that ran in a few minutes instead of a day. The warehouse ran on a cloud data platform with separate compute for loading and for dashboards. Most of the logic was set-based queries with window functions and common table expressions.

I used ETL to move data from the CRM into the warehouse nightly. I used Airflow to schedule the refresh. I shared a short written plan in the first week so nobody was surprised by scope later. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Results

Within the first quarter the system delivered fresh data by 7am every day. Data access took longer than the build itself; getting the right permissions was a project of its own. Demos happened every Friday, which kept feedback small and frequent. The first version was deliberately boring, and that is why it shipped on time. We tracked a small set of numbers weekly and dropped anything nobody looked at. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I wrote the documentation as I went instead of at the end, which made the handover painless. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Handover included a recorded walkthrough and a short runbook for whoever is on call. The insurance team had strong opinions about edge cases, and most of them turned out to be right. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

Code: github.com/praman-data/nightly-sync
