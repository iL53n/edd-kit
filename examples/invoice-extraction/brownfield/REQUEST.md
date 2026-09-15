# Synthetic existing-application preparation request

Prepare evaluations before implementing support for `Total: USD 1,234.56` and
`Total: EUR 2,345.60` in this existing offline invoice extractor. For this bounded
test fixture, the new convention is a line labelled exactly `Total:`, then the
explicit USD/EUR currency and an amount using comma-separated groups of three
digits and exactly two decimal places. Return the inline currency and an ungrouped
two-decimal total string. Preserve the existing ungrouped/separate-Currency format.
Subtotal alone is not a Total. Conflicting explicit Total amounts are null while
a consistent currency remains known; conflicting currencies are null.

Keep full input unchanged. Do not alter application behavior during Prepare.
There is no prior EDD project or eval suite here, and no provider is available.
Labels and approval declarations are synthetic workflow-test fixtures only, not
human approval or production-domain evidence. Other grammar, rounding, symbols,
locale conventions and precedence decisions are outside this small test.
