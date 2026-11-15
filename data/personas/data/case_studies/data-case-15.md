---
id: data-case-15
title: School Results Analysis
project: school-results
skills:
- r
- statistics
date: 2023-11
client_industry: education
outcome: paused
---

# School Results Analysis

This engagement started with a complaint from the operations lead: the district had ten years of results in separate spreadsheets.
Most of the hard problems were about messy inputs rather than clever algorithms. I shared a short written plan in the first week so nobody was surprised by scope later. The client's own staff can now extend it without me, which was an explicit goal.

## What I did

Duplicate customers were merged, broken dates repaired and free-text country names standardised. I used ggplot2 to run the survey models and charts. I used regression to separate signal from noise.

Finance received a workbook with lookups, pivot tables and a protected assumptions tab they could edit themselves. Security review asked for audit logs on every action, so we added them early. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## Results

Within the first quarter the system analysed 5 years of results. We deliberately left out two features the client asked for at the start because they did not move the main metric. A pilot with one team came first; the wider rollout followed after two weeks of fixes. I wrote the documentation as I went instead of at the end, which made the handover painless. Data access took longer than the build itself; getting the right permissions was a project of its own. The education team had strong opinions about edge cases, and most of them turned out to be right. We tracked a small set of numbers weekly and dropped anything nobody looked at. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The first version was deliberately boring, and that is why it shipped on time. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Demos happened every Friday, which kept feedback small and frequent.

## Stack

tidyverse, hypothesis testing, plus the usual tooling.
