---
id: fullstack-case-02
title: Clinic Booking Portal
project: clinic-booking
skills:
- react
- node.js
date: 2023-04
client_industry: healthcare
outcome: handed over
---

# Clinic Booking Portal

The brief was simple to state and hard to do: patients booked by phone and the front desk double-booked rooms, and the healthcare business wanted that fixed.
Most of the hard problems were about messy inputs rather than clever algorithms. The client's own staff can now extend it without me, which was an explicit goal. Handover included a recorded walkthrough and a short runbook for whoever is on call.

## What I did

Routes, auth middleware and error handling were layered as a classic minimal HTTP framework app. I used PostgreSQL to store orders and users relationally. I used NodeJS to run the backend services. I used React to build the component library and screens.

Users signed in with their existing Google or Microsoft accounts and tokens were refreshed silently. Styling used utility classes and a shared design-token config instead of hand-written stylesheets. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The healthcare team had strong opinions about edge cases, and most of them turned out to be right.

## Results

Measured against the old process, it moved 36% of bookings online. Security review asked for audit logs on every action, so we added them early. I wrote the documentation as I went instead of at the end, which made the handover painless. Demos happened every Friday, which kept feedback small and frequent. I shared a short written plan in the first week so nobody was surprised by scope later. The first version was deliberately boring, and that is why it shipped on time. We tracked a small set of numbers weekly and dropped anything nobody looked at. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Data access took longer than the build itself; getting the right permissions was a project of its own. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Stack

react, Node, plus the usual tooling.
