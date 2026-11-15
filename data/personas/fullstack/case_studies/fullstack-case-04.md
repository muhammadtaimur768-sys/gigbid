---
id: fullstack-case-04
title: Shopify Wholesale Portal
project: shopify-wholesale
skills:
- shopify
- react
date: 2024-04
client_industry: ecommerce
outcome: delivered
---

# Shopify Wholesale Portal

The brief was simple to state and hard to do: wholesale buyers emailed orders that staff re-keyed, and the ecommerce business wanted that fixed.
We deliberately left out two features the client asked for at the start because they did not move the main metric. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## What I did

The backend was a small set of JavaScript services running on the server runtime with worker queues. I used react to build the component library and screens. I used Shopify Liquid to extend the merchant's storefront.

Clients asked for exactly the fields they needed through a single typed schema endpoint. Security review asked for audit logs on every action, so we added them early. Data access took longer than the build itself; getting the right permissions was a project of its own.

## Results

The headline number: it processed 35 wholesale orders a month. We started with a two-day discovery session to agree on what success would look like and how it would be measured. The client's own staff can now extend it without me, which was an explicit goal. We tracked a small set of numbers weekly and dropped anything nobody looked at. The first version was deliberately boring, and that is why it shipped on time. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. I wrote the documentation as I went instead of at the end, which made the handover painless. I shared a short written plan in the first week so nobody was surprised by scope later. The ecommerce team had strong opinions about edge cases, and most of them turned out to be right. Most of the hard problems were about messy inputs rather than clever algorithms. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## Stack

Shopify Liquid, react, plus the usual tooling.
