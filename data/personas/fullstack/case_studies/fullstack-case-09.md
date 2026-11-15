---
id: fullstack-case-09
title: CI/CD and Containerisation
project: devops-pipeline
skills:
- docker
- ci/cd
- aws
date: 2025-04
client_industry: fintech
outcome: paused
---

# CI/CD and Containerisation

In April 2025 I was asked to help a mid-sized fintech company where deploys were done by SSH-ing into a server on Friday nights.
I shared a short written plan in the first week so nobody was surprised by scope later. We started with a two-day discovery session to agree on what success would look like and how it would be measured. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## What I did

I used aws to host the app and file uploads. Data lived in a relational database with foreign keys, row-level security and nightly backups. The backend was a small set of JavaScript services running on the server runtime with worker queues.

I used CI/CD to ship every merged pull request automatically. I used docker to make local and production environments match. The fintech team had strong opinions about edge cases, and most of them turned out to be right. The first version was deliberately boring, and that is why it shipped on time.

## Results

The headline number: it went from monthly to 15 deploys a week. Most of the hard problems were about messy inputs rather than clever algorithms. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We tracked a small set of numbers weekly and dropped anything nobody looked at. I wrote the documentation as I went instead of at the end, which made the handover painless. Handover included a recorded walkthrough and a short runbook for whoever is on call. Demos happened every Friday, which kept feedback small and frequent. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Data access took longer than the build itself; getting the right permissions was a project of its own. The client's own staff can now extend it without me, which was an explicit goal. Security review asked for audit logs on every action, so we added them early.

## Stack

Docker Compose, GitHub Actions, plus the usual tooling.

Code: github.com/dmartins-dev/shipyard
