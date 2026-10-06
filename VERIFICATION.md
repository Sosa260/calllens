# Build verification

Latest automated test run: 6 October 2026. All 11 tests passed. Local server verification below was performed on 24 September 2026.

- 11 automated tests pass: core metrics, six scenario regressions, unknown handling, size limits, evidence validation, CSV escaping, schema validation, mocked API adapters and two Streamlit interaction tests.
- The Streamlit tests exercise call evaluation, the offline benchmark and hiding a report when its inputs change.
- Local server started successfully; health endpoint returned `ok`.
- Dependencies tested: Python 3.12, Streamlit 1.64.0, OpenAI SDK 2.54.0, Pydantic 2.13.5. Direct dependency versions are pinned in `requirements.txt`.
- Live transcription and evaluation requests were not sent. They require an authorized API key. Provider tests use mocks, not real API responses.
- A browser screenshot review was unavailable because the browser automation service failed to start. Automated dashboard interactions passed.

Reproduce from the project folder with `python -m unittest discover -s tests -v` after installing requirements.
