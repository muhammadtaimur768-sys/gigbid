---
id: fullstack-case-18
title: End-to-End Test Suite
project: e2e-test-suite
skills:
- playwright testing
- ci/cd
date: 2023-10
client_industry: travel
outcome: delivered
---

# End-to-End Test Suite

The brief was simple to state and hard to do: every release broke checkout for some browser, and the travel business wanted that fixed.
We deliberately left out two features the client asked for at the start because they did not move the main metric. Most of the hard problems were about messy inputs rather than clever algorithms. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## What I did

I used e2e testing to test the critical flows end to end. I used ci/cd to ship every merged pull request automatically. Every service ran from the same image locally and in production, started with one compose command.

Types were shared between the server and the browser, so a renamed field broke the build instead of production. The client's own staff can now extend it without me, which was an explicit goal. Security review asked for audit logs on every action, so we added them early.

## Results

Within the first quarter the system cut checkout incidents by 62%. The first version was deliberately boring, and that is why it shipped on time. I shared a short written plan in the first week so nobody was surprised by scope later. Demos happened every Friday, which kept feedback small and frequent. The travel team had strong opinions about edge cases, and most of them turned out to be right. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Data access took longer than the build itself; getting the right permissions was a project of its own. A pilot with one team came first; the wider rollout followed after two weeks of fixes. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Handover included a recorded walkthrough and a short runbook for whoever is on call. I wrote the documentation as I went instead of at the end, which made the handover painless.

## Stack

playwright testing, ci/cd, plus the usual tooling.

Code: github.com/dmartins-dev/safetynet
