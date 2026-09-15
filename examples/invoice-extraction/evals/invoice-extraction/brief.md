# Invoice extraction: proposed preimplementation criteria

The user requests full invoice text in and JSON with `currency` (`USD`, `EUR`, or
null) and `total` (a decimal string with exactly two places or null) out. Only an
explicitly labelled Total is eligible; Subtotal is not. Missing or ambiguous
fields are null. No external services are available. This is a new project and
the request is prepare-only; generated goldens have not been reviewed.

## Prepared coverage

Twelve synthetic invoices cover USD/EUR, distinct Subtotal/Total, one-decimal and
integer amounts, missing fields, conflicting totals/currencies, unsupported
currency, zero, Amount due without Total, and full Unicode/CRLF/footer input.
The six development cases are a subset of the twelve acceptance cases. Each case
maps to schema, currency and total requirements. Positive and negative controls
exercise each metric separately, including valid JSON formatting alternatives,
duplicate keys, invented values and selecting one conflicting value.

All expected outputs and control labels are agent-authored proposals derived from
this brief, not human-approved truth or sampled production data. `reviewed_by`
was left null in the original Prepare-only exercise. Calibration controls are separate from validation controls; local
validation is not a protected holdout. Three deterministic native DeepEval metrics
compare observations with the proposed references. They do not implement invoice
extraction. At original preparation the only target was an explicitly identified stub returning two nulls.
The later synthetic Build-to-Check exercise added the separate application target.

## Preserve all invoice text

Every fixture retains the complete source string without stripping, truncating or
normalizing it. The independent test-only `harness_checks.py` sends each complete
source through EDD's target transport to an echo probe and checks exact equality,
including Unicode, CRLF and trailing spaces. It also checks the original fixture
bytes were not modified. This establishes evaluation transport and fixture
preservation, not future product-internal storage. The requested two-field output
does not include source text; if preservation means persisting or returning the
original invoice, that interface decision remains open before implementation.

## Review decisions still required

- The proposed cases treat ambiguity independently per field: a conflicting
  currency does not erase a clearly labelled total, and vice versa.
- Unsupported currency maps to null. Integer and one-decimal source amounts are
  formatted to two places without changing their numeric value.
- JSON key order and whitespace are immaterial. Leading zeros in a decimal
  string are currently permitted; a canonical numeric spelling was not requested.
- This first slice does not decide currency-symbol interpretation, locale number
  separators, the full grammar/case of Total labels, multiple-invoice inputs or
  credit/negative-total semantics. Add agreed examples before claiming coverage.
- Confirm whether preservation concerns the evaluation's full input transport or
  also persistent application storage; the latter needs an observable interface.

## Preparation handoff

Inspect the suite, exercise the real graders on these unreviewed controls, run
the preservation harness, and record the acceptance-profile stub baseline.
Expected baseline failures demonstrate only the stub's absence of extraction.
Audit agreement cannot establish review or domain correctness. Generate `REVIEW.md` for discussion,
but do not record an `approve` decision until the user approves the actual current criteria and labels.
No production feature work is authorized by this preparation-only request.

## Subsequent isolated workflow-test authorization

The coordinator subsequently requested a bounded Build-to-Check skill test in
this disposable workspace. The original user's goldens are still not approved
for a real product. For this synthetic test only, the worked examples and control
labels were checked against this brief and use the explicit fixture provenance
`EDD synthetic workflow test`; this is not human or production-domain approval.
The test takes lossless full-input transport (not persistent storage) as its scope,
retains the existing independent-field ambiguity and number-format assumptions,
and does not expand coverage to the unresolved grammar/locale cases above.
No case outcome, metric logic or acceptance threshold is changed for this test.
Only scratch target implementation, ordinary tests and local evidence are now
authorized. The original prepare-only handoff remains historical evidence summarized in the example README.
