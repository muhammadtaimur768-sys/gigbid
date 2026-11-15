---
id: aiml-case-08
title: Radiology Report Structuring
project: radiology-report-nlp
skills:
- nlp
- python
date: 2023-02
client_industry: healthcare
outcome: delivered
---

# Radiology Report Structuring

The brief was simple to state and hard to do: free-text radiology reports could not be searched or audited, and the healthcare business wanted that fixed.
I wrote the documentation as I went instead of at the end, which made the handover painless. Handover included a recorded walkthrough and a short runbook for whoever is on call. Demos happened every Friday, which kept feedback small and frequent.

## What I did

A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class. I used nlp to pull entities and intents out of free text. I used py to glue the data pipeline and model code together.

We started from a pretrained encoder checkpoint and only trained the last layers on the client's data. We deliberately left out two features the client asked for at the start because they did not move the main metric. The healthcare team had strong opinions about edge cases, and most of them turned out to be right.

## Results

The headline number: it structured 35 reports per day. We tracked a small set of numbers weekly and dropped anything nobody looked at. I shared a short written plan in the first week so nobody was surprised by scope later. We started with a two-day discovery session to agree on what success would look like and how it would be measured. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Data access took longer than the build itself; getting the right permissions was a project of its own. Security review asked for audit logs on every action, so we added them early. The client's own staff can now extend it without me, which was an explicit goal. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The first version was deliberately boring, and that is why it shipped on time. Most of the hard problems were about messy inputs rather than clever algorithms.

## Stack

nlp, python3, plus the usual tooling.
