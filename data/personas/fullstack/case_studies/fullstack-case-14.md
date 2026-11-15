---
id: fullstack-case-14
title: Headless Product Catalogue
project: headless-catalog
skills:
- mongodb
- express
date: 2024-05
client_industry: retail
outcome: handed over
---

# Headless Product Catalogue

A retail client came to me because products had very different attributes and the old schema could not cope.
We deliberately left out two features the client asked for at the start because they did not move the main metric. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I shared a short written plan in the first week so nobody was surprised by scope later.

## What I did

Types were shared between the server and the browser, so a renamed field broke the build instead of production. I used express to define the REST routes and middleware. I used MongoDB to store the flexible product catalogue.

Every service ran from the same image locally and in production, started with one compose command. The backend was a small set of JavaScript services running on the server runtime with worker queues. Handover included a recorded walkthrough and a short runbook for whoever is on call. I wrote the documentation as I went instead of at the end, which made the handover painless.

## Results

Measured against the old process, it indexed 7k products. We tracked a small set of numbers weekly and dropped anything nobody looked at. Data access took longer than the build itself; getting the right permissions was a project of its own. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Security review asked for audit logs on every action, so we added them early. The retail team had strong opinions about edge cases, and most of them turned out to be right. Most of the hard problems were about messy inputs rather than clever algorithms. The client's own staff can now extend it without me, which was an explicit goal. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Demos happened every Friday, which kept feedback small and frequent. The first version was deliberately boring, and that is why it shipped on time.

## Stack

mongodb, express, plus the usual tooling.
