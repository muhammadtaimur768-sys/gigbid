---
id: fullstack-case-10
title: Restaurant Online Ordering
project: restaurant-ordering
skills:
- next.js
- stripe
date: 2024-11
client_industry: hospitality
outcome: handed over
---

# Restaurant Online Ordering

In November 2024 I was asked to help a mid-sized hospitality company where the group paid a third-party app a large commission on every order.
The client's own staff can now extend it without me, which was an explicit goal. I wrote the documentation as I went instead of at the end, which made the handover painless. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## What I did

I used Next.js to server-render the marketing and app pages. I used stripe to handle subscriptions and invoices. Styling used utility classes and a shared design-token config instead of hand-written stylesheets.

The board updated live for every viewer without refreshing, over a persistent connection. Data lived in a relational database with foreign keys, row-level security and nightly backups. Data access took longer than the build itself; getting the right permissions was a project of its own. The first version was deliberately boring, and that is why it shipped on time.

## Results

The headline number: it moved 26% of orders to their own site. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Security review asked for audit logs on every action, so we added them early. The hospitality team had strong opinions about edge cases, and most of them turned out to be right. We tracked a small set of numbers weekly and dropped anything nobody looked at. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Demos happened every Friday, which kept feedback small and frequent. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call. Most of the hard problems were about messy inputs rather than clever algorithms. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Stack

next.js, Stripe payments, plus the usual tooling.
