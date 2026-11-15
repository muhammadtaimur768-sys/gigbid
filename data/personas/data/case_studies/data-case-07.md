---
id: data-case-07
title: CRM Deduplication and Clean-Up
project: crm-cleanup
skills:
- data cleaning
- python
date: 2023-06
client_industry: wholesale
outcome: delivered
---

# CRM Deduplication and Clean-Up

This engagement started with a complaint from the operations lead: a third of the CRM records were duplicates.
I wrote the documentation as I went instead of at the end, which made the handover painless. The client's own staff can now extend it without me, which was an explicit goal. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## What I did

Finance received a workbook with lookups, pivot tables and a protected assumptions tab they could edit themselves. Exports from three systems were reshaped, merged on customer keys and pivoted in memory. I used data quality to fix duplicates and broken dates.

I used Python to automate the monthly refresh. I shared a short written plan in the first week so nobody was surprised by scope later. Security review asked for audit logs on every action, so we added them early.

## Results

Within the first quarter the system merged 39k duplicate records. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Most of the hard problems were about messy inputs rather than clever algorithms. The wholesale team had strong opinions about edge cases, and most of them turned out to be right. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We deliberately left out two features the client asked for at the start because they did not move the main metric. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The first version was deliberately boring, and that is why it shipped on time. We tracked a small set of numbers weekly and dropped anything nobody looked at. Data access took longer than the build itself; getting the right permissions was a project of its own.

## Stack

data quality, python, plus the usual tooling.

Code: github.com/praman-data/dedupe-crm
