---
id: fullstack-case-06
title: Course Platform for an Online School
project: lms-platform
skills:
- next.js
- stripe
date: 2023-11
client_industry: education
outcome: delivered
---

# Course Platform for an Online School

A education client came to me because the school sold courses through three disconnected tools.
We tracked a small set of numbers weekly and dropped anything nobody looked at. Demos happened every Friday, which kept feedback small and frequent. The education team had strong opinions about edge cases, and most of them turned out to be right.

## What I did

Users signed in with their existing Google or Microsoft accounts and tokens were refreshed silently. Uploads went straight to object storage with signed URLs and the app ran in the client's cloud account. Product records with very different attributes were stored as flexible documents with compound indexes.

I used stripe to handle subscriptions and invoices. I used next.js to server-render the marketing and app pages. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## Results

Measured against the old process, it served 6 students. The client's own staff can now extend it without me, which was an explicit goal. The first version was deliberately boring, and that is why it shipped on time. We deliberately left out two features the client asked for at the start because they did not move the main metric. We started with a two-day discovery session to agree on what success would look like and how it would be measured. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Data access took longer than the build itself; getting the right permissions was a project of its own. Most of the hard problems were about messy inputs rather than clever algorithms. Security review asked for audit logs on every action, so we added them early. I wrote the documentation as I went instead of at the end, which made the handover painless. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## Stack

Next.js, payments, plus the usual tooling.
