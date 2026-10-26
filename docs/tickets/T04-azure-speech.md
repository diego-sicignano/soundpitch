# T04. Azure AI Speech with a real key

**Depends on:** none (needs an Azure Speech resource)  **Acceptance:** S14  **Spec:** §14

## Goal

The Azure neural voices work for real, in the page and from the command line.

## Steps

1. Create an Azure AI Speech resource; note the region and the price tier. Put `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` in `backend/.env`. Never commit them.
2. **Test first:** `backend/tests/test_check_speech.py` with the stubbed HTTP client of `test_api.py`: success writes the file and exits 0, a failure prints the message and exits 1.
3. Implement `backend/app/check_speech.py` using `tts.synthesize`.
4. **Page:** limit prefetch to 3 requests in flight (already the case in `frontend/app.js`; add an e2e test that mocks `/api/tts` with a route and checks it, and that a `501` falls back to the browser voice with a message in `status`).
5. **S14 (manual):** run `check_speech` for `en` and `it`, listen, and save a short mp3 and a screenshot of the page with the Azure voice selected in `docs/evidence/` (keep each file small).

## Verification

Same commands as T02.

## Out of scope

Custom neural voices, SSML styles, real-time streaming synthesis.
