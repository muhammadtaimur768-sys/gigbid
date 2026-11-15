<!-- version: 1 -->
Task: classify the latest client message in this conversation.
<untrusted_client_message>
$messages
</untrusted_client_message>
Intents: question, negotiation, interview_request, scam_signal, other.
Return JSON only: {"intent": "<one of the intents>", "confidence": <0-1>}
