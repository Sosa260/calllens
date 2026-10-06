from pathlib import Path
import hashlib
import json
import os
import time
import streamlit as st
from evaluator import baseline, csv_report, word_error_rate
from provider import evaluate_live, transcribe

st.set_page_config(page_title="CallLens · Voice agent evaluation", page_icon="◉", layout="wide")
ROOT = Path(__file__).parent
CALLS = json.loads((ROOT / "data/calls.json").read_text())

st.title("CallLens")
st.caption("VOICE AGENT EVALUATION · PORTFOLIO PROTOTYPE")
st.write("Review what happened in a call, inspect the evidence, and identify what needs attention.")

with st.sidebar:
    st.header("Evaluation settings")
    mode = st.radio("Evaluator", ["Offline baseline", "Live AI evaluation"])
    st.caption("Offline mode uses transparent phrase rules. It does not call an AI service.")
    key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("EVALUATION_MODEL", "gpt-4.1-mini")
    asr_model = os.getenv("TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
    consent = False
    if mode == "Live AI evaluation":
        key = st.text_input("OpenAI API key", value=key, type="password")
        model = st.text_input("Evaluation model", value=model)
        asr_model = st.text_input("Transcription model", value=asr_model)
        st.caption("Live actions send the selected content to OpenAI and may incur API charges. The key is kept only in this session.")
        consent = st.checkbox("This is synthetic or authorized data, and I agree to send it for analysis.")
    st.divider()
    st.write("**Rubric: 0–2 per dimension**")
    st.caption("Acknowledgement · Action clarity · Outcome confirmation · Handoff")
    st.caption("Unknown items are excluded from the score. Always read the coverage and quotes.")

review, benchmark, methodology = st.tabs(["Review a call", "Synthetic benchmark", "Method & limits"])
with review:
    source = st.selectbox("Transcript source", [x["title"] for x in CALLS] + ["Paste a transcript", "Upload a transcript", "Transcribe audio"])
    initial = ""
    source_key = source
    if source in [x["title"] for x in CALLS]:
        initial = next(x["transcript"] for x in CALLS if x["title"] == source)
    elif source == "Upload a transcript":
        file = st.file_uploader("UTF-8 text file", type=["txt"])
        if file:
            if file.size > 150000:
                st.error("Use a text file under 150 KB.")
            else:
                try:
                    initial = file.getvalue().decode("utf-8-sig")
                    source_key += hashlib.sha256(file.getvalue()).hexdigest()
                except UnicodeDecodeError:
                    st.error("Save the transcript as UTF-8 text and upload it again.")
    elif source == "Transcribe audio":
        st.info("Audio requires live mode. Review the resulting text and add Customer: / Agent: labels before evaluation; this transcription path does not identify speakers.")
        audio = st.file_uploader("Synthetic or authorized recording · up to 20 MB", type=["wav", "mp3", "m4a", "webm", "mp4"])
        audio_id = hashlib.sha256(audio.getvalue()).hexdigest() if audio else "none"
        if audio:
            st.audio(audio)
        if st.button("Transcribe recording", disabled=not (audio and mode == "Live AI evaluation" and consent and key)):
            try:
                with st.spinner("Transcribing…"):
                    raw = transcribe(audio.getvalue(), audio.name, key, asr_model)
                st.session_state["audio_" + audio_id] = raw
                st.session_state.pop("text_" + source + audio_id, None)
            except Exception:
                st.error("Transcription failed. Check your key, model access, audio format and connection, then retry.")
        initial = st.session_state.get("audio_" + audio_id, "")
        source_key += audio_id
    text = st.text_area("Transcript · one speaker turn per line", value=initial, height=245, key="text_" + source_key)
    reference = st.text_area("Optional human reference transcript for word error rate", height=80)
    st.caption("For audio, WER compares the original ASR output against your reference, before your edits. For other sources it compares the text above.")
    fingerprint = hashlib.sha256((text + reference + mode + model).encode()).hexdigest()
    if st.button("Evaluate call", type="primary", disabled=mode == "Live AI evaluation" and not (key and consent)):
        try:
            started = time.perf_counter()
            with st.spinner("Evaluating…"):
                result = baseline(text) if mode == "Offline baseline" else evaluate_live(text, key, model)
            result["evaluation_seconds"] = round(time.perf_counter() - started, 3)
            if reference.strip():
                result["asr_metrics"] = word_error_rate(reference, initial if source == "Transcribe audio" else text)
            st.session_state["evaluation"] = (fingerprint, result)
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("Evaluation failed. Check the API key, model access and connection. No successful result was recorded.")
    saved = st.session_state.get("evaluation")
    if saved and saved[0] == fingerprint:
        result = saved[1]
        a, b, c, d = st.columns(4)
        a.metric("Observed outcome", result["outcome"].title())
        b.metric("Intent", result["intent"].replace("_", " ").title())
        c.metric("Rubric score", "Unknown" if result["quality_percent"] is None else f"{result['quality_percent']:.0f}%")
        d.metric("Dimensions assessed", f"{result['coverage']} / 4")
        st.caption(f"{result['mode']} · {result['model']} · evaluator processing time {result['evaluation_seconds']}s (not agent response latency)")
        st.write(result["summary"])
        if result["outcome_evidence"]:
            st.text("Outcome evidence: " + result["outcome_evidence"])
        st.dataframe(result["rubric"], hide_index=True, width="stretch")
        for flag in result["flags"]:
            st.warning(flag)
        st.write("**Next review step:** " + result["next_action"])
        if "asr_metrics" in result:
            metrics = result["asr_metrics"]
            st.metric("Word error rate", f"{metrics['word_error_rate']:.1%}")
            st.caption(f"{metrics['word_edits']} word edits / {metrics['reference_words']} reference words. WER can exceed 100%.")
        left, right = st.columns(2)
        left.download_button("Download full JSON report", json.dumps(result, indent=2), "call-evaluation.json", "application/json")
        right.download_button("Download rubric CSV", csv_report(result), "call-rubric.csv", "text/csv")
    elif saved:
        st.info("Inputs have changed. Evaluate again to show a report for the current call.")

with benchmark:
    st.write("Six authored scenarios test basic behaviour, including pending refunds, contradictory outcomes and an instruction embedded in a call.")
    st.caption("Expected labels are author-defined. This is a small regression set, not an estimate of real-world accuracy.")
    if st.button("Run offline benchmark"):
        rows = []
        for call in CALLS:
            result = baseline(call["transcript"])
            rows.append({"scenario": call["id"], "expected": call["expected_outcome"], "observed": result["outcome"], "intent": result["intent"], "matches": result["outcome"] == call["expected_outcome"] and result["intent"] == call["expected_intent"]})
        st.dataframe(rows, hide_index=True, width="stretch")
        st.write(f"{sum(r['matches'] for r in rows)} / {len(rows)} scenarios match both expected labels.")

with methodology:
    st.markdown((ROOT / "METHOD.md").read_text())
