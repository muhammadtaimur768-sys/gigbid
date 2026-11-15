---
id: aiml-case-06
title: Brand-Voice Fine-Tune for Marketing Copy
project: llm-tone-finetune
skills:
- llm fine-tuning
- huggingface transformers
date: 2023-01
client_industry: marketing
outcome: paused
---

# Brand-Voice Fine-Tune for Marketing Copy

The brief was simple to state and hard to do: the agency's copy from hosted models sounded generic and cost too much per draft, and the marketing business wanted that fixed.
Security review asked for audit logs on every action, so we added them early. Demos happened every Friday, which kept feedback small and frequent. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## What I did

I used huggingface transformers to start from a pretrained encoder. Training ran on rented GPU instances in the client's cloud account and the endpoint scaled to zero at night. We wrote our own training loop with mixed precision and gradient accumulation to fit a single 24 GB card.

I used llm fine-tuning to adapt an open model to the client's tone and labels. A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class. The first version was deliberately boring, and that is why it shipped on time. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## Results

The headline number: it cut cost per draft by 53%. Handover included a recorded walkthrough and a short runbook for whoever is on call. Most of the hard problems were about messy inputs rather than clever algorithms. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. The client's own staff can now extend it without me, which was an explicit goal. Data access took longer than the build itself; getting the right permissions was a project of its own. I wrote the documentation as I went instead of at the end, which made the handover painless. The marketing team had strong opinions about edge cases, and most of them turned out to be right. I shared a short written plan in the first week so nobody was surprised by scope later. We deliberately left out two features the client asked for at the start because they did not move the main metric.

## Stack

LoRA fine-tuning, Hugging Face, plus the usual tooling.
