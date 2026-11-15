---
id: aiml-case-19
title: Multilingual Ticket Classifier
project: multilingual-classifier
skills:
- huggingface transformers
- llm fine-tuning
date: 2023-11
client_industry: travel
outcome: paused
---

# Multilingual Ticket Classifier

A travel client came to me because tickets in six languages waited in one queue.
We tracked a small set of numbers weekly and dropped anything nobody looked at. Security review asked for audit logs on every action, so we added them early. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## What I did

I used huggingface transformers to start from a pretrained encoder. We wrote our own training loop with mixed precision and gradient accumulation to fit a single 24 GB card. I used LoRA fine-tuning to adapt an open model to the client's tone and labels.

Free-text tickets were tagged with intents and the names, dates and amounts inside them were extracted automatically. The whole service shipped as one image the client's ops team could run with a single command. I shared a short written plan in the first week so nobody was surprised by scope later. Demos happened every Friday, which kept feedback small and frequent.

## Results

Measured against the old process, it routed 23% of tickets automatically. The client's own staff can now extend it without me, which was an explicit goal. The travel team had strong opinions about edge cases, and most of them turned out to be right. A pilot with one team came first; the wider rollout followed after two weeks of fixes. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. Most of the hard problems were about messy inputs rather than clever algorithms. We started with a two-day discovery session to agree on what success would look like and how it would be measured. Handover included a recorded walkthrough and a short runbook for whoever is on call. The first version was deliberately boring, and that is why it shipped on time. Data access took longer than the build itself; getting the right permissions was a project of its own. I wrote the documentation as I went instead of at the end, which made the handover painless.
