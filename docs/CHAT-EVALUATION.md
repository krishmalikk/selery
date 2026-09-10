# Chat evidence evaluation

The fixed questions are in `tests/fixtures/chat-evaluation-questions.json`. Run the offline evidence gate with:

```sh
PYTHONPATH=apps/api:packages/shared/python:packages/strategies/python .venv/bin/python -m pytest tests/test_chat_context.py
```

The six cases cover a next-session question with stale data, explanation of a selected signal, absent confidence, conflicting reports, incomplete history, and an unsupported public-trader motive. The runnable tests inspect the evidence delivered to the assistant and its explicit missing-data rules. Separate regression cases verify causal ATR, future-bar mutation, provisional observations, holidays, DST, early closes, historical signal snapshots, outcome availability, context size, and IEX feature restrictions.

These tests do not establish that a live model obeyed those instructions. They make no paid requests. They do not measure live answer latency, provider cost, citation precision or a model's continuity across turns. A manual paid evaluation remains a separate operation under the existing $5 monthly cap and kill switch.

For each manual answer, record the exact question, answer ID, model/version, UTC retrieval and completion times, recorded cost, and the provided citation IDs. Review every quoted price/date/percentage against its source; record unsupported claims, unrecognized citation IDs, whether unavailable confidence stayed unavailable, and whether the second turn preserves context without treating prior answers as new evidence. Do not mark acceptance complete on an attractive answer alone.

Current context limitations: bounded retrieval is keyword-based rather than an arbitrary model tool; session coverage requires complete aligned five-minute observations, so thin IEX coverage can legitimately leave session levels unavailable; news is limited to three published reports and does not establish causal impact; corporate-action adjustment and full extended-hours coverage remain unverified. SPY cost comparisons use explicitly assumed spread cases and an effective-dated schedule. Dates beyond the schedule's verified coverage return unavailable costs. Other stocks require explicit symbol-specific assumptions before a cost calculation is supplied.
