# Prepare the missing inline-total convention

The fixed synthetic policy is in `REQUEST.md`; this brief does not expand it.
The project originally contained only `app/target.py` and REQUEST.md, with no EDD
configuration or evaluation suite. Read the actual parser before preparing tests:
it reads labelled lines, uses separate `Currency:`, accepts ungrouped numeric
`Total:`, and withholds conflicting values. Its existing JSON process boundary
can be used directly; no new adapter or production change is needed to evaluate.

Direct discovery executed `Currency: USD\nTotal: 12.50\n` and observed USD/12.50.
It executed `Total: USD 1,234.56\n` and observed null/null. These are actual
existing-application results, not a fabricated weak stub.

The authored pipeline has six full-source cases, three native deterministic
graders and eight requirement-specific positive/negative controls. It covers the
new inline grouped amounts, legacy format, Subtotal exclusion, conflicting totals
and a Unicode/CRLF/footer input. Reference outcomes and control labels are fixed
synthetic workflow-test fixtures checked against REQUEST.md, not human approval
or production evidence. No model grader, API or provider is required.

Reuse the known metric interface for structured invoice fields; do not implement
parsing in the evaluator. The baseline target is the unchanged existing app,
kind=application. No candidate implementation or stub has been generated for this
prepare-only extension. All source invoice characters remain in the fixture.

Remaining grammar, malformed grouping, currency precedence, storage and locale
questions are explicitly outside the supplied small test policy. Preparation
does not claim they are solved. The next real product action would be review of
those decisions and the actual drafted examples, not automatic implementation.
