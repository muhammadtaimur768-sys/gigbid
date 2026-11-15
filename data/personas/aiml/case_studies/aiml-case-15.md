---
id: aiml-case-15
title: Drone Imagery Crop Health
project: crop-yield-cv
skills:
- computer vision
- aws
date: 2024-07
client_industry: agriculture
outcome: paused
---

# Drone Imagery Crop Health

The brief was simple to state and hard to do: agronomists walked fields to spot disease too late, and the agriculture business wanted that fixed.
The first version was deliberately boring, and that is why it shipped on time. A pilot with one team came first; the wider rollout followed after two weeks of fixes. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## What I did

I used aws to host training jobs and endpoints. We wrote our own training loop with mixed precision and gradient accumulation to fit a single 24 GB card. I used CV to detect defects in the line-camera images.

The whole service shipped as one image the client's ops team could run with a single command. We tracked a small set of numbers weekly and dropped anything nobody looked at. Most of the hard problems were about messy inputs rather than clever algorithms.

## Results

Within the first quarter the system flagged disease 3 days earlier. Handover included a recorded walkthrough and a short runbook for whoever is on call. Data access took longer than the build itself; getting the right permissions was a project of its own. The client's own staff can now extend it without me, which was an explicit goal. I shared a short written plan in the first week so nobody was surprised by scope later. I wrote the documentation as I went instead of at the end, which made the handover painless. Demos happened every Friday, which kept feedback small and frequent. We deliberately left out two features the client asked for at the start because they did not move the main metric. Security review asked for audit logs on every action, so we added them early. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The agriculture team had strong opinions about edge cases, and most of them turned out to be right.
