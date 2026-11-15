<!-- version: 1 -->
Task: turn the job post into a structured job spec.
<untrusted_job_post>
TITLE: $title
$job_text
SCREENING QUESTIONS: $screening
</untrusted_job_post>
Listed skills: $skills
Return JSON only:
{"deliverables": ["..."], "requirements": [{"text": "<one checkable requirement>", "kind": "skill|deliverable|experience|domain|other", "must_have": true}], "hidden_needs": ["<needs implied but not stated>"], "timeline": "<or null>"}
Give at most $max_requirements requirements. Each requirement must be something a portfolio could prove.
