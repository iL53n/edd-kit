# Independently authored invoice evaluation example

This fixture came from an independent coding-agent exercise of **Prepare → Build
→ Check**, not from the bundled cancellation template. It is synthetic workflow
evidence, not an approved invoice product or a claim about model quality.

## Original request

Prepare before implementation: given full text of an invoice, output JSON with
`currency` (`USD`, `EUR`, or null) and `total` (decimal string with exactly two
places or null). Extract an explicitly labelled Total, never Subtotal. Missing
or ambiguous fields are null. Preserve all text. No external services are
available; preparation must not implement the feature or self-approve goldens.

Prepare produced twelve full-text cases, three native DeepEval graders, twenty
proposed controls (six calibration, fourteen validation), and a null-only stub.
It stopped with no review decisions or production target. The declared synthetic controls can be
audited, but neither their provenance nor a passing audit is domain or technical approval. The
genuine stub baseline had schema12/12,
currency4/12,total4/12. The full-text transport check passed12/12.

A separately authorized synthetic workflow continuation seeded an explicitly
labelled test review—not actual user approval—then used the installed Build and
Check skills. Ordinary JSON-process tests went red→green. Dev evaluations caught
two field-ambiguity defects before their fix. Fresh Check audit passed14/14 and
application acceptance36/36; verify PASS with a comparable stub baseline. Progress
was reread through a new CLI invocation; this tests file/process-based resumption,
not an independent model context reset. No goldens, metric logic or thresholds
changed during implementation; Check did not modify the application.

## Run the retained source

Use the package's hashed evaluator dependency lock as described in
`evals/invoice-extraction/dependencies.md`. Activate that environment so `edd`,
`python` and `python3` resolve consistently. From this directory:

```bash
edd inspect invoice-extraction --json
python -m unittest discover -s tests -v
python evals/invoice-extraction/harness_checks.py
edd audit invoice-extraction
edd run invoice-extraction --target stub --stage baseline --profile acceptance
# Expected baseline exit 1: valid observations establish missing stub behavior.
edd run invoice-extraction --target candidate --stage candidate --profile acceptance
edd verify invoice-extraction
```

No `review.json` or generated `REVIEW.md` is shipped. Verification remains INCONCLUSIVE until you
generate and commit the packet, record actual domain approval, run the audit, and separately record
technical validation. The existing `reviewed_by` strings are legacy synthetic provenance, not human
review of your application. Do not reuse them as approval when adapting it.

This deterministic parser is deliberately limited to the input conventions in
the brief. Full-text preservation means lossless evaluation input transport; the
two-field output does not prove persistent source storage. Unknown locale,
rounding, currency-symbol and label-precedence decisions remain outside the slice.

## Existing application, no prior eval suite

`brownfield/` is a separate project with the unchanged existing parser under
`app/target.py` and a preparation-only extension. Its fixed request is support for
`Total: USD 1,234.56` / `Total: EUR 2,345.60`, preserving the legacy format.

The independent exercise started with **only the app and request**, no EDD project
or suite. It read the parser and observed legacy USD/12.50 working while the new
inline convention returned null/null. Prepare generated six new cases, three
graders, eight controls and a direct existing-application baseline. Audit passed8/8;
the genuine application baseline failed7/18 observations, with schema6/6,
currency2/6,total3/6. Text transport passed6/6. Its application hash remained
unchanged. No inline-total implementation was written.

Run `edd --root brownfield inspect inline-total --json`,
`edd --root brownfield audit inline-total`, and
`edd --root brownfield run inline-total --target current --stage baseline --profile acceptance`.
The expected baseline exits1; there is intentionally no candidate implementation.
Synthetic control provenance is not a production review decision here either.

## Archived execution identity and portability

Observed on macOS/Python3.12.11, installed EDD0.1.0 and DeepEval4.2.3. All graders
reported zero cost and no provider was called. The fixed test wheel preceded some
later source fixes; these historical results do not certify the final release.

- Original frozen Build/Check criteria digest:
  `6ee659a1aedd1b1f6cbad9afda94dc652450d25fd58e127ef33eb56770cc9df2`.
- Original brownfield criteria digest:
  `b526bcade1fd4fa584756f1338f3781c7bfef4834580e654b6ee16326129a132`.
- Application bytes before/after Check and brownfield Prepare:
  `3ffaece2919445b54525d846399997ada73b3b610f8b476a24caca2df3d3edcb`.
- Original golden bytes remained
  `f11d7904da38f00c0b847ad63923b571e4f42288ddfe4cae1da11df1471d37ca`.

For portability this retained copy replaces absolute interpreter paths with
`python3`, replaces local dependency notes/dumps with the packaged-lock reference,
and clarifies historical brief wording. No semantic cases, control labels or
metric logic were changed. Artifact and runtime identity consequently differ;
obtain fresh review, audit, baseline and acceptance rather than transplanting old
evidence. Review events are portable declarations bound to criteria,
not machine authentication. Raw `.edd` history, review events, installed skills
and copied dependency locks are intentionally excluded from this source example.
