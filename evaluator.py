"""Conservative, reproducible baseline and evidence validation. No network calls."""
from __future__ import annotations
import csv
import io
import re
from datetime import datetime, timezone

MAX_CHARS = 30000
RUBRIC_VERSION = "1.0"
DIMENSIONS = ["acknowledgement", "action_clarity", "outcome_confirmation", "handoff"]


def validate_transcript(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("Add a transcript before evaluating.")
    if len(text) > MAX_CHARS:
        raise ValueError(f"Keep the transcript under {MAX_CHARS:,} characters.")
    return text


def turns(text: str) -> list[tuple[str, str]]:
    result = []
    for line in text.splitlines():
        match = re.match(r"^\s*(Customer|Agent)\s*:\s*(.+)$", line, re.I)
        if match:
            result.append((match[1].lower(), line.strip()))
    return result


def find_line(lines, pattern):
    return next((line for line in lines if re.search(pattern, line, re.I)), "")


def item(dimension, score=None, evidence="", reason="Insufficient evidence to assess."):
    return dict(dimension=dimension, score=score, evidence=evidence, reason=reason)


def baseline(text: str) -> dict:
    text = validate_transcript(text)
    parsed = turns(text)
    customer = [line for role, line in parsed if role == "customer"]
    agent = [line for role, line in parsed if role == "agent"]
    customer_text = " ".join(customer).lower()
    intent = "unknown"
    for label, pattern in [("billing", r"refund|charged|invoice|billing"), ("account_access", r"password|log.?in|sign.?in|locked out"), ("appointment", r"appointment|booking|reschedule"), ("cancellation", r"cancel|unsubscribe"), ("technical_support", r"broken|not working|error|offline")]:
        if re.search(pattern, customer_text):
            intent = label
            break
    # Inspect the final customer turn. Later contradictory statements override earlier success.
    last = customer[-1] if customer else ""
    unresolved = find_line([last], r"still|not fixed|not resolved|cannot|can't|didn't|did not|doesn't|does not|not working")
    resolved = find_line([last], r"(?:that|it) (?:works|worked|fixed it)|can log in now|received the refund|confirmed.*(?:booking|appointment)|issue is resolved")
    handoff = find_line(agent, r"(?:transfer|escalat|specialist|human agent|support team)")
    outcome = "unresolved" if unresolved else "resolved" if resolved else "escalated" if handoff else "unknown"
    outcome_evidence = unresolved or resolved or handoff
    acknowledgement = find_line(agent, r"sorry|understand|help you|help with")
    action = find_line(agent, r"please (?:open|click|check|try)|(?:sent|created|submitted|booked|scheduled|transferring)")
    handoff_detail = find_line(agent, r"(?:ticket|reference|within|by tomorrow|hours)")
    rubric = [
        item("acknowledgement", 1 if acknowledgement else None, acknowledgement, "Acknowledgement phrase found; relevance needs human review." if acknowledgement else "No supported judgement from the baseline."),
        item("action_clarity", 1 if action else None, action, "An action phrase is present; completeness needs review." if action else "No supported judgement from the baseline."),
        item("outcome_confirmation", 2 if resolved and not unresolved else 0 if unresolved else None, unresolved or resolved, "Final customer statement indicates an outcome." if unresolved or resolved else "No explicit customer confirmation found."),
        item("handoff", 1 if handoff else None, handoff, "Handoff mentioned; verify ownership and timing." if handoff else "Handoff not established or not applicable."),
    ]
    flags = []
    if re.search(r"ignore (?:all |previous )?instructions|give.*(?:full|perfect).*score", text, re.I):
        flags.append("Possible instruction embedded in transcript; review as call content only.")
    if not customer or not agent:
        flags.append("Missing Customer: / Agent: labels; baseline coverage is limited.")
    if handoff and not handoff_detail:
        flags.append("Handoff lacks a detected ticket or timing phrase.")
    result = dict(mode="Offline baseline", model="rules-v1", rubric_version=RUBRIC_VERSION,
                  intent=intent, summary=("Customer opening: " + customer[0].split(":", 1)[1].strip()) if customer else "No labelled customer turn found.",
                  outcome=outcome, outcome_evidence=outcome_evidence, rubric=rubric,
                  flags=flags, next_action="Review evidence and confirm the outcome against business records.")
    return finalize(result, text)


def finalize(result: dict, text: str) -> dict:
    """Reject invented quotations, preserve unknowns, and expose score coverage."""
    result = dict(result)
    result["rubric"] = [dict(row) for row in result["rubric"]]
    result["flags"] = list(result["flags"])
    for row in result["rubric"]:
        if row["score"] is not None and (not row["evidence"].strip() or row["evidence"] not in text):
            row.update(score=None, reason="Evidence quote could not be verified in the transcript.", evidence="")
            result["flags"].append(f"Unverified evidence: {row['dimension']}.")
    if result["outcome"] != "unknown" and (not result["outcome_evidence"].strip() or result["outcome_evidence"] not in text):
        result["outcome"] = "unknown"
        result["outcome_evidence"] = ""
        result["flags"].append("Outcome evidence could not be verified.")
    scored = [row["score"] for row in result["rubric"] if row["score"] is not None]
    result["coverage"] = len(scored)
    result["quality_percent"] = round(sum(scored) / (2 * len(scored)) * 100, 1) if scored else None
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    result["transcript"] = text
    return result


def word_error_rate(reference: str, hypothesis: str) -> dict:
    # Ignore speaker labels and punctuation; retain apostrophes within words.
    def tokens(s):
        s = re.sub(r"(?im)^\s*(customer|agent)\s*:", "", s)
        return re.findall(r"\w+(?:['’]\w+)?", s.lower())
    ref, hyp = tokens(reference), tokens(hypothesis)
    if not ref:
        raise ValueError("Reference transcript must contain words.")
    if max(len(ref), len(hyp)) > 3000:
        raise ValueError("WER comparison is limited to 3,000 words per transcript.")
    previous = list(range(len(hyp) + 1))
    for i, a in enumerate(ref, 1):
        current = [i]
        for j, b in enumerate(hyp, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b)))
        previous = current
    edits = previous[-1]
    return {"word_error_rate": edits / len(ref), "word_edits": edits, "reference_words": len(ref)}


def csv_report(result: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["dimension", "score_0_to_2", "evidence", "reason"])
    for row in result["rubric"]:
        # Spreadsheet formula injection protection for user/model-controlled text.
        values = [row["dimension"], row["score"], row["evidence"], row["reason"]]
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v for v in values])
    return output.getvalue()
