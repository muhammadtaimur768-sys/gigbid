---
id: fullstack-case-15
title: SSO and Auth Overhaul
project: auth-overhaul
skills:
- oauth
- node.js
date: 2023-02
client_industry: saas
outcome: delivered
---

# SSO and Auth Overhaul

This engagement started with a complaint from the operations lead: enterprise customers required SSO before signing.
When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We tracked a small set of numbers weekly and dropped anything nobody looked at. Security review asked for audit logs on every action, so we added them early.

## What I did

Data lived in a relational database with foreign keys, row-level security and nightly backups. I used node.js to run the backend services. Sessions, rate-limit counters and hot queries sat in an in-memory key-value store in front of the database.

I used oauth to let users sign in with Google and Microsoft. Checkout and sign-up were exercised in a real headless browser on every pull request. A pilot with one team came first; the wider rollout followed after two weeks of fixes. I shared a short written plan in the first week so nobody was surprised by scope later.

## Results

Within the first quarter the system unblocked 30 enterprise deals. Handover included a recorded walkthrough and a short runbook for whoever is on call. Demos happened every Friday, which kept feedback small and frequent. We deliberately left out two features the client asked for at the start because they did not move the main metric. The first version was deliberately boring, and that is why it shipped on time. The saas team had strong opinions about edge cases, and most of them turned out to be right. Most of the hard problems were about messy inputs rather than clever algorithms. I wrote the documentation as I went instead of at the end, which made the handover painless. Data access took longer than the build itself; getting the right permissions was a project of its own. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The client's own staff can now extend it without me, which was an explicit goal.

## Stack

oauth, node.js, plus the usual tooling.

Code: github.com/dmartins-dev/keyring
