---
id: fullstack-case-01
title: Invoicing SaaS from Zero to Paying Customers
project: invoicing-saas
skills:
- next.js
- stripe
date: 2025-02
client_industry: saas
outcome: delivered
---

# Invoicing SaaS from Zero to Paying Customers

In February 2025 I was asked to help a mid-sized saas company where the founder had a Figma file and a waiting list but no product.
Most of the hard problems were about messy inputs rather than clever algorithms. The first version was deliberately boring, and that is why it shipped on time. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## What I did

I used NextJS to server-render the marketing and app pages. The schema was declared once and migrations plus a typed query client came out of it. Types were shared between the server and the browser, so a renamed field broke the build instead of production. Checkout and sign-up were exercised in a real headless browser on every pull request.

I used PostgreSQL to store orders and users relationally. I used Stripe to handle subscriptions and invoices. Data access took longer than the build itself; getting the right permissions was a project of its own. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## Results

Within the first quarter the system reached 37 paying customers in three months. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The client's own staff can now extend it without me, which was an explicit goal. Demos happened every Friday, which kept feedback small and frequent. We deliberately left out two features the client asked for at the start because they did not move the main metric. The saas team had strong opinions about edge cases, and most of them turned out to be right. I shared a short written plan in the first week so nobody was surprised by scope later. Security review asked for audit logs on every action, so we added them early. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We tracked a small set of numbers weekly and dropped anything nobody looked at.

Code: github.com/dmartins-dev/billbird
