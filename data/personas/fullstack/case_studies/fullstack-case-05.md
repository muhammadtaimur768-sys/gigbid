---
id: fullstack-case-05
title: Courier Tracking Mobile App
project: delivery-tracking-app
skills:
- react native
- node.js
date: 2025-05
client_industry: logistics
outcome: delivered
---

# Courier Tracking Mobile App

This engagement started with a complaint from the operations lead: drivers phoned dispatch to confirm every drop-off.
When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The logistics team had strong opinions about edge cases, and most of them turned out to be right. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## What I did

Types were shared between the server and the browser, so a renamed field broke the build instead of production. I used react native to ship the iOS and Android apps from one codebase. The board updated live for every viewer without refreshing, over a persistent connection.

Data lived in a relational database with foreign keys, row-level security and nightly backups. I used NodeJS to run the backend services. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## Results

The headline number: it cut dispatch calls by 47%. The client's own staff can now extend it without me, which was an explicit goal. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Most of the hard problems were about messy inputs rather than clever algorithms. Security review asked for audit logs on every action, so we added them early. Data access took longer than the build itself; getting the right permissions was a project of its own. Demos happened every Friday, which kept feedback small and frequent. I wrote the documentation as I went instead of at the end, which made the handover painless. We deliberately left out two features the client asked for at the start because they did not move the main metric. We tracked a small set of numbers weekly and dropped anything nobody looked at. The first version was deliberately boring, and that is why it shipped on time.

## Stack

react native, NodeJS, plus the usual tooling.
