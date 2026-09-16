# Strict acceptance workflow

Use this branch only when the user needs a formal acceptance decision rather than ordinary development feedback.

1. Complete the feature-specific requirements, cases, metrics, fixtures, and target identity.
2. Add reviewed positive and negative validation controls for every requirement. Keep calibration examples separate from validation evidence.
3. Run `edd audit CHANGE` and fix false passes, false failures, and execution gaps.
4. Generate `edd review CHANGE --write`. Record explicit domain and technical decisions for the current criteria digest.
5. Record a comparable acceptance-profile baseline when useful:

   ```bash
   edd run CHANGE --target TARGET --stage baseline --profile acceptance
   ```

   If it cannot exist, use `edd baseline-unavailable CHANGE --reason TEXT` rather than fabricating one.

6. Run the consolidated gate:

   ```bash
   edd check CHANGE --target TARGET --report-dir .edd/CHANGE/report --revision REVISION
   ```

7. Read the generated report and individual evidence. Explain the control audit, candidate acceptance, baseline comparability, target provenance, and every incomplete or critical result.

Use `edd status CHANGE --acceptance` to inspect strict readiness. Criteria changes make affected review, audit, and baseline evidence stale; preserve old runs and refresh the evidence for the new bundle.
