---
id: aiml-case-12
title: Invoice Data Extraction
project: invoice-extraction
skills:
- computer vision
- nlp
date: 2024-05
client_industry: accounting
outcome: delivered
---

# Invoice Data Extraction

In May 2024 I was asked to help a mid-sized accounting company where staff typed totals and VAT numbers from scanned invoices.
I wrote the documentation as I went instead of at the end, which made the handover painless. Data access took longer than the build itself; getting the right permissions was a project of its own. The client's own staff can now extend it without me, which was an explicit goal.

## What I did

Everything from the ingestion scripts to the training loop lived in one typed codebase with a small CLI. I used computer vision to detect defects in the line-camera images. We iterated on the instructions and few-shot examples until the outputs matched the client's template every time.

I used nlp to pull entities and intents out of free text. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not. We tracked a small set of numbers weekly and dropped anything nobody looked at.

## Results

The headline number: it automated 42% of invoice fields. I shared a short written plan in the first week so nobody was surprised by scope later. Demos happened every Friday, which kept feedback small and frequent. We deliberately left out two features the client asked for at the start because they did not move the main metric. The first version was deliberately boring, and that is why it shipped on time. Handover included a recorded walkthrough and a short runbook for whoever is on call. Security review asked for audit logs on every action, so we added them early. A pilot with one team came first; the wider rollout followed after two weeks of fixes. Most of the hard problems were about messy inputs rather than clever algorithms. The accounting team had strong opinions about edge cases, and most of them turned out to be right. We started with a two-day discovery session to agree on what success would look like and how it would be measured.

## Stack

CV, natural language processing, plus the usual tooling.
