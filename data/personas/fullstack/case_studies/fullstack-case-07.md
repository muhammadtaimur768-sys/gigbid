---
id: fullstack-case-07
title: GraphQL API for a Rental Marketplace
project: marketplace-api
skills:
- graphql
- node.js
date: 2026-09
client_industry: real estate
outcome: delivered
---

# GraphQL API for a Rental Marketplace

In September 2026 I was asked to help a mid-sized real estate company where the web and mobile teams kept asking backend for new endpoints.
The real estate team had strong opinions about edge cases, and most of them turned out to be right. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## What I did

I used graphql to give the mobile and web clients one flexible API. Sessions, rate-limit counters and hot queries sat in an in-memory key-value store in front of the database. I used node.js to run the backend services. Every service ran from the same image locally and in production, started with one compose command.

Types were shared between the server and the browser, so a renamed field broke the build instead of production. I used postgresql to store orders and users relationally. Most of the hard problems were about messy inputs rather than clever algorithms. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## Results

Measured against the old process, it cut p95 latency to 71 ms. The first version was deliberately boring, and that is why it shipped on time. Data access took longer than the build itself; getting the right permissions was a project of its own. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I shared a short written plan in the first week so nobody was surprised by scope later. The client's own staff can now extend it without me, which was an explicit goal. We deliberately left out two features the client asked for at the start because they did not move the main metric. Security review asked for audit logs on every action, so we added them early. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

Code: github.com/dmartins-dev/rentql
