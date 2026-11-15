# LinkedIn write-up

How to post it: on LinkedIn, click **Write article** (not "Start a post"), paste the title and the article body below, add `docs/images/` diagrams if you like, and publish. Then make a normal post with the **short post** text and the article link.

---

## Short post (paste as a normal LinkedIn post, with the article link)

I built GigBid, a multi-agent copilot that finds freelance jobs, flags scams and prompt-injected posts, and drafts proposals in which every claim has to point at real portfolio evidence. A human approves every send.

The most surprising result wasn't about models at all. Swapping retrieval algorithms barely mattered. One metadata filter took evidence Recall@5 from 0.012 to 0.522. And better retrieval didn't automatically mean more client replies.

The write-up covers what I measured, what failed (including the reranker), and what I'd ship. 👇
[link to article]

#LangGraph #RAG #MCP #AIEngineering #Freelancing

---

## Article

### Title: The best retrieval upgrade in my agent system was a filter, not a model

I spent a few weeks building GigBid, a multi-agent system that helps a freelancer bid on jobs. A Scout pulls new posts. A Job Analyst, a Risk Assessor and a Fit Matcher run in parallel. A Pricing Strategist decides whether the bid is worth its Connects. A Writer drafts the proposal, a verifier checks every claim against the portfolio, a Critic can send the draft back up to twice, and a Compliance Guard enforces the marketplace rules. Nothing leaves the system until a human approves it in the UI, and the graph literally pauses on a LangGraph interrupt until they do.

The architecture is the part people ask about. But the result I keep thinking about is a retrieval number, and it isn't the one I expected.

#### The setup

Every proposal claim has to be backed by evidence: a case study, a repository, a client review. If the portfolio doesn't support "I've built RAG chatbots for legal teams", that sentence gets removed before the Critic ever sees the draft. So retrieval decides what the writer is *allowed* to say. Bad retrieval doesn't just make proposals generic. It makes them shorter and weaker, because unsupported claims get cut.

The test corpus was built to be hostile to naive RAG. There are three freelancer personas (an AI/ML engineer, a full-stack developer and a data analyst). Each has a CV, 17–19 case studies, 5–7 repositories with code, a dozen client reviews, and **150 past proposals** labelled won, replied or ignored. The same project is described three different ways: by its slug in the case study, a codename in the repo, and a casual description in a review. Skills are often implied by code rather than named in a README.

I evaluated retrieval against gold evidence labels on 60 seeded dev jobs per persona: Recall@5, MRR and nDCG@10, macro-averaged over the personas.

#### What I expected

My written hypothesis, recorded before the full run, was the standard one. Decompose each job into its requirements and retrieve per requirement, then add hybrid BM25 + dense retrieval for exact library names like "dbt" or "Celery". I predicted that combination would beat the naive baseline by about 15 points of Recall@5.

I implemented the usual menu as configurable components: naive dense (V0), requirement decomposition (V1), hybrid with reciprocal rank fusion (V2), cross-encoder reranking (V3), outcome-aware boosting from proposals that won (V4), multi-vector items that index summary, README and code separately but return one project (V5), and a corrective loop that grades evidence and refuses to claim when it's weak (V8).

#### What actually happened

In a 40-job pilot, **every variant scored essentially zero**. The naive baseline's Recall@5 on the full run was 0.012.

The cause was mundane. Those 150 past proposals per persona paraphrase job titles. A job titled "Deploy our ML models to production on AWS" is semantically closest to *a past proposal that answered a similar job*, not to the case study that proves you've actually done MLOps. The proposals swamped every ranking. Dense, sparse, reranked: it didn't matter what was doing the ranking, because the wrong *type* of document was winning.

The fix was a component I hadn't planned: evidence-type routing. When the question is "what proves this requirement?", search only case studies and repositories. Proposals are useful for *tone* and outcome learning, not as proof.

Routing alone moved Recall@5 from **0.012 to 0.522**. In the ablation of the final pipeline, removing the routing step drops Recall@5 by **0.605**, essentially all of it. Removing hybrid retrieval costs 0.042. Removing multi-vector indexing costs 0.011.

The shipped pipeline is routing + hybrid + multi-vector: **Recall@5 0.605, MRR 0.977, nDCG@10 0.777**, with a p95 retrieval time around 0.6 s on a laptop CPU.

My original hypothesis failed. Decomposition plus hybrid gained 6 points over the routed baseline, not 15. I recorded the routing component as an amendment to the hypothesis *before* the full run, which matters if you want the numbers to mean anything.

#### Things that made it worse

Three of the techniques I expected to help made things worse.

- **The cross-encoder reranker lowered recall** (0.522 vs 0.594 without it) and added seconds per job. It's an ms-marco web-search model. It's good at "does this passage answer this query", and bad at "does this paragraph imply this person knows Kubernetes".
- **Outcome-aware boosting hurt MRR** (0.909 → 0.792). Evidence that a proposal *won* is not evidence of a skill. Mixing "what worked" into "what's true" blurred both.
- **The corrective loop refused too much.** It correctly refused on 61% of jobs with no real evidence, which is exactly the "jobs this persona should skip" behaviour you want. But it also falsely refused on 13% of jobs that did have evidence. That refusal signal is more useful as an input to the bid/skip decision than as a retriever.

#### The second surprise: better retrieval didn't buy more replies

The marketplace simulator has clients with hidden preferences: must-have skills, a budget ceiling, and a dislike of generic openings. They decide whether to reply. So I could measure outcomes, not just retrieval scores.

With the open-weight `gpt-oss-20b` writer on 40 dev jobs, the agent's proposals had a much higher mean reply *probability* than a generic template (0.60 vs 0.33). But the actual simulated reply rate on that small sample was 0.36 vs 0.43 for the template (n = 14 proposals each).

That's a small sample and I'd want ten times more before drawing a conclusion. Still, it lines up with something the per-claim evidence showed. Once retrieval is "good enough" to surface the right project, the remaining reply-rate gap comes from things retrieval can't fix: price relative to the client's ceiling, an opening line that sounds like every other bid, and length. Retrieval is a gate, not a lever. Past a threshold, more of it doesn't move the outcome.

A separate A/B test inside the simulator backs this up. Two proposal *strategies* using the same retrieval differed significantly in reply rate: 72.1% vs 55.1% over 147 jobs per arm, two-proportion z = 3.03, p = 0.0024. How you write, given the evidence, mattered more than squeezing out another few points of Recall@5.

#### What I'd tell someone building a RAG system for an agent

1. **Look at what's winning before you tune how it wins.** I almost spent a day comparing rerankers on a pipeline whose problem was document type. A ten-minute look at the top-5 results for a handful of queries would have shown it.
2. **Metadata is retrieval.** Every chunk carried persona, type, project, skills, date, client industry and outcome. That metadata turned out to be the single most valuable part of the index.
3. **Write the hypothesis down first, including the number.** "Hybrid will help" is unfalsifiable. "+15 points of Recall@5 on jobs with 4+ requirements" can fail, and mine did. That's the useful kind of result.
4. **Measure the outcome, not just the proxy.** nDCG going up is not the goal. The goal is a client replying to a proposal that only says true things.
5. **Negative results are results.** Reranking didn't help here, and I can explain why. That's worth more than an unmeasured "we added a reranker".

#### Caveats, because they matter

The corpus, the marketplace and the clients are synthetic, generated for this project, so absolute numbers won't transfer to a real marketplace. The dev set and some decision thresholds come from the same generator and I had no held-out split, so the decision metrics are optimistic. Latencies were measured on a busy laptop and on a free-tier hosted model with rate limits. The architecture comparison (single ReAct agent vs a prebuilt supervisor vs the hand-built graph) ran on only 8 jobs and is indicative at best.

#### The stack, for the curious

LangGraph for the two graphs (bid and conversation), with parallel branches via `Send`, bounded critique loops, interrupts for approval and a Postgres checkpointer so a pending approval survives a crash. Three MCP servers built on the official Python SDK (portfolio, marketplace and workspace), one marketplace port that targets either the simulator or a live marketplace through its official MCP server, FastAPI with Server-Sent Events, and a React + TypeScript UI. Models are open-weight: `gpt-oss-20b`/`120b` hosted for the deployed app, and qwen2.5 and mistral 7B locally for comparison. Embeddings and reranking run on CPU.

The code, evaluation runners and every results file behind the numbers above are public. The portfolio MCP server can be installed on its own with a single `uvx` command if you want to point it at your own case studies.

*Repo: https://github.com/muhammadtaimur768-sys/gigbid · Live demo: https://gigbid-gamma.vercel.app*
