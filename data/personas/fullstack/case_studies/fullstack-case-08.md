---
id: fullstack-case-08
title: jQuery to React Migration
project: legacy-migration
skills:
- react
- typescript
date: 2025-01
client_industry: insurance
outcome: extended
---

# jQuery to React Migration

In January 2025 I was asked to help a mid-sized insurance company where a ten-year-old jQuery admin panel broke whenever anyone touched it.
We tracked a small set of numbers weekly and dropped anything nobody looked at. We deliberately left out two features the client asked for at the start because they did not move the main metric. Data access took longer than the build itself; getting the right permissions was a project of its own.

## What I did

Every merge ran lint, tests and a preview deploy, and tagging a release promoted it to production. I used React.js to build the component library and screens. Checkout and sign-up were exercised in a real headless browser on every pull request.

I used typescript to keep the front and back end type-safe. A pilot with one team came first; the wider rollout followed after two weeks of fixes. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Results

The headline number: it removed 36k lines of legacy code. The first version was deliberately boring, and that is why it shipped on time. I shared a short written plan in the first week so nobody was surprised by scope later. Handover included a recorded walkthrough and a short runbook for whoever is on call. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The client's own staff can now extend it without me, which was an explicit goal. Demos happened every Friday, which kept feedback small and frequent. The insurance team had strong opinions about edge cases, and most of them turned out to be right. I wrote the documentation as I went instead of at the end, which made the handover painless. Security review asked for audit logs on every action, so we added them early. Most of the hard problems were about messy inputs rather than clever algorithms.

## Stack

react, TS, plus the usual tooling.
