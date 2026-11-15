---
id: fullstack-case-12
title: Event Ticketing with QR Check-In
project: event-ticketing
skills:
- node.js
- stripe
- redis
date: 2024-06
client_industry: events
outcome: delivered
---

# Event Ticketing with QR Check-In

In June 2024 I was asked to help a mid-sized events company where the festival's ticket provider crashed on release day.
Demos happened every Friday, which kept feedback small and frequent. Security review asked for audit logs on every action, so we added them early. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## What I did

I used redis to cache sessions and rate limits. Every service ran from the same image locally and in production, started with one compose command. I used Stripe to handle subscriptions and invoices. The interface was split into small reusable components with hooks for data fetching and form state.

I used NodeJS to run the backend services. Uploads went straight to object storage with signed URLs and the app ran in the client's cloud account. We deliberately left out two features the client asked for at the start because they did not move the main metric. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Results

Measured against the old process, it sold 29 tickets in the first hour. Most of the hard problems were about messy inputs rather than clever algorithms. Data access took longer than the build itself; getting the right permissions was a project of its own. The client's own staff can now extend it without me, which was an explicit goal. The events team had strong opinions about edge cases, and most of them turned out to be right. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Handover included a recorded walkthrough and a short runbook for whoever is on call. A pilot with one team came first; the wider rollout followed after two weeks of fixes. I shared a short written plan in the first week so nobody was surprised by scope later. I wrote the documentation as I went instead of at the end, which made the handover painless.

## Stack

node.js, Stripe payments, plus the usual tooling.

Code: github.com/dmartins-dev/gatepass
