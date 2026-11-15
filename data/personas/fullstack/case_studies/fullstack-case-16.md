---
id: fullstack-case-16
title: Fitness Coaching App
project: fitness-app
skills:
- react native
- typescript
date: 2023-09
client_industry: fitness
outcome: delivered
---

# Fitness Coaching App

A fitness client came to me because the trainer sent workout plans as PDFs on messaging apps.
I shared a short written plan in the first week so nobody was surprised by scope later. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## What I did

Uploads went straight to object storage with signed URLs and the app ran in the client's cloud account. I used typescript to keep the front and back end type-safe. Customers paid by card on a hosted checkout, and webhook events kept subscription status in sync.

I used react native to ship the iOS and Android apps from one codebase. We deliberately left out two features the client asked for at the start because they did not move the main metric. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## Results

Measured against the old process, it reached 30 active subscribers. Security review asked for audit logs on every action, so we added them early. The fitness team had strong opinions about edge cases, and most of them turned out to be right. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I wrote the documentation as I went instead of at the end, which made the handover painless. The client's own staff can now extend it without me, which was an explicit goal. Demos happened every Friday, which kept feedback small and frequent. Data access took longer than the build itself; getting the right permissions was a project of its own. The first version was deliberately boring, and that is why it shipped on time. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Most of the hard problems were about messy inputs rather than clever algorithms.
