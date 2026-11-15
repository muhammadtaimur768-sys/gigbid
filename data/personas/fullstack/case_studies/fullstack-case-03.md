---
id: fullstack-case-03
title: Real-Time Collaboration Board
project: realtime-kanban
skills:
- react
- websockets
date: 2022-02
client_industry: agency
outcome: handed over
---

# Real-Time Collaboration Board

This engagement started with a complaint from the operations lead: the agency's planning lived in a spreadsheet that people overwrote.
Demos happened every Friday, which kept feedback small and frequent. Most of the hard problems were about messy inputs rather than clever algorithms. I wrote the documentation as I went instead of at the end, which made the handover painless.

## What I did

The backend was a small set of JavaScript services running on the server runtime with worker queues. I used React to build the component library and screens. Types were shared between the server and the browser, so a renamed field broke the build instead of production.

Sessions, rate-limit counters and hot queries sat in an in-memory key-value store in front of the database. I used websockets to push live updates to the browser. We tracked a small set of numbers weekly and dropped anything nobody looked at. I shared a short written plan in the first week so nobody was surprised by scope later.

## Results

Within the first quarter the system supported 29 concurrent editors. The agency team had strong opinions about edge cases, and most of them turned out to be right. Security review asked for audit logs on every action, so we added them early. Data access took longer than the build itself; getting the right permissions was a project of its own. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Handover included a recorded walkthrough and a short runbook for whoever is on call. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The client's own staff can now extend it without me, which was an explicit goal. The first version was deliberately boring, and that is why it shipped on time. We deliberately left out two features the client asked for at the start because they did not move the main metric. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Stack

react, websockets, plus the usual tooling.

Code: github.com/dmartins-dev/pinboard-live
