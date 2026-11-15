---
id: fullstack-case-13
title: Donation Platform for a Charity
project: nonprofit-donations
skills:
- next.js
- stripe
date: 2024-07
client_industry: nonprofit
outcome: extended
---

# Donation Platform for a Charity

The brief was simple to state and hard to do: monthly donors churned because updating a card meant calling the office, and the nonprofit business wanted that fixed.
We deliberately left out two features the client asked for at the start because they did not move the main metric. Handover included a recorded walkthrough and a short runbook for whoever is on call. Data access took longer than the build itself; getting the right permissions was a project of its own.

## What I did

I used Stripe payments to handle subscriptions and invoices. I used NextJS to server-render the marketing and app pages. Data lived in a relational database with foreign keys, row-level security and nightly backups.

The schema was declared once and migrations plus a typed query client came out of it. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## Results

The headline number: it raised recurring donations by 61%. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Most of the hard problems were about messy inputs rather than clever algorithms. I shared a short written plan in the first week so nobody was surprised by scope later. Demos happened every Friday, which kept feedback small and frequent. The first version was deliberately boring, and that is why it shipped on time. The nonprofit team had strong opinions about edge cases, and most of them turned out to be right. The client's own staff can now extend it without me, which was an explicit goal. We tracked a small set of numbers weekly and dropped anything nobody looked at. I wrote the documentation as I went instead of at the end, which made the handover painless. Security review asked for audit logs on every action, so we added them early.
