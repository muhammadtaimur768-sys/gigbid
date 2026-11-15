---
id: aiml-case-04
title: Weld Defect Detection on the Line
project: weld-defect-detection
skills:
- computer vision
- pytorch
date: 2025-05
client_industry: manufacturing
outcome: handed over
---

# Weld Defect Detection on the Line

In May 2025 I was asked to help a mid-sized manufacturing company where manual inspection missed hairline cracks on the night shift.
Handover included a recorded walkthrough and a short runbook for whoever is on call. Data access took longer than the build itself; getting the right permissions was a project of its own. A pilot with one team came first; the wider rollout followed after two weeks of fixes.

## What I did

I used computer vision to detect defects in the line-camera images. Everything from the ingestion scripts to the training loop lived in one typed codebase with a small CLI. The whole service shipped as one image the client's ops team could run with a single command.

I used pytorch to train the custom model heads. A held-out set labelled by the client's experts decided every change, and we reported precision and recall per class. The first version was deliberately boring, and that is why it shipped on time. When the scope changed halfway through, we re-planned in an afternoon rather than pretending it had not.

## Results

The headline number: it caught 36% more defects than manual inspection. We deliberately left out two features the client asked for at the start because they did not move the main metric. Security review asked for audit logs on every action, so we added them early. Demos happened every Friday, which kept feedback small and frequent. The client's own staff can now extend it without me, which was an explicit goal. Most of the hard problems were about messy inputs rather than clever algorithms. We tracked a small set of numbers weekly and dropped anything nobody looked at. We started with a two-day discovery session to agree on what success would look like and how it would be measured. I shared a short written plan in the first week so nobody was surprised by scope later. I wrote the documentation as I went instead of at the end, which made the handover painless.

Code: github.com/aokafor-ml/weldscope
