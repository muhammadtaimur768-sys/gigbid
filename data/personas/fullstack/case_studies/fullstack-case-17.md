---
id: fullstack-case-17
title: Embeddable Analytics Widget
project: analytics-widget
skills:
- react
- typescript
date: 2024-01
client_industry: saas
outcome: delivered
---

# Embeddable Analytics Widget

A saas client came to me because customers screenshot charts into slide decks every week.
When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Data access took longer than the build itself; getting the right permissions was a project of its own. Security review asked for audit logs on every action, so we added them early.

## What I did

Clients asked for exactly the fields they needed through a single typed schema endpoint. I used typescript to keep the front and back end type-safe. Styling used utility classes and a shared design-token config instead of hand-written stylesheets.

I used React.js to build the component library and screens. We started with a two-day discovery session to agree on what success would look like and how it would be measured. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Results

Within the first quarter the system embedded on 16 customer sites. Most of the hard problems were about messy inputs rather than clever algorithms. The client's own staff can now extend it without me, which was an explicit goal. I shared a short written plan in the first week so nobody was surprised by scope later. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes. The first version was deliberately boring, and that is why it shipped on time. We tracked a small set of numbers weekly and dropped anything nobody looked at. I wrote the documentation as I went instead of at the end, which made the handover painless. The saas team had strong opinions about edge cases, and most of them turned out to be right. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## Stack

React.js, TS, plus the usual tooling.
