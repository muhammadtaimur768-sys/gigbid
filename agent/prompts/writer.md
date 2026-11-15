<!-- version: 1 -->
Task: write a cover letter for this job on behalf of the freelancer.
Strategy: $strategy_desc
Freelancer: $name, $title_line.
Job (third-party data):
<untrusted_job_post>
TITLE: $title
$job_text
</untrusted_job_post>
Requirements to address: $requirements
Evidence you may cite (ONLY these facts may be claimed; cite the item id in square brackets, e.g. [aiml-case-03]):
<untrusted_evidence>
$evidence
</untrusted_evidence>
Bid: $price
Style rules learned from the user's edits: $style_rules
What has worked before in this category: $outcome_hints
Critic feedback to fix (may be empty): $feedback
Rules: do not open with a generic greeting such as "Dear Sir", "I am a passionate" or "Hi, I read your job".
Open with the client's problem. No email addresses, phone numbers or off-platform contact. Between
$min_chars and $max_chars characters. Do not claim any experience that is not in the evidence above.
Screening questions to answer (one short answer each): $screening
Return JSON only: {"cover_letter": "...", "screening_answers": [{"question": "...", "answer": "..."}]}
