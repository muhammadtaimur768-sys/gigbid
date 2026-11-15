<!-- version: 1 -->
Task: review this proposal draft as a demanding client would.
Job requirements: $requirements
Screening questions: $screening
Automatic checks: $checks
<untrusted_draft>
$draft
</untrusted_draft>
Score 0-10 on: addresses the client's actual problem, specific evidence for each must-have requirement,
no generic opening, concise, answers every screening question, no unsupported claims.
Return JSON only: {"score": <0-10>, "verdict": "pass|revise", "reasons": ["<concrete fix>", "..."]}
