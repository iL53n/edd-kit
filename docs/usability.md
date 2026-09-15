# Engineer–SME pilot protocol

Use this protocol with two independent engineer–SME pairs on a genuine LLM-backed feature. Select
invoice extraction only if a participant owns a real ambiguous extraction problem; do not add an
LLM merely to make the deterministic example look realistic. Use 20–30 sanitized cases with
ambiguous inputs, missing information, legitimate alternatives, and known failures.

## Tasks

1. The engineer prepares the suite and committed `REVIEW.md`; an independent contributor supplies
   at least some plausible failure controls.
2. The SME reviews Markdown only, records meaningful feedback, and does not read Python or JSON.
3. The engineer makes an explicit canonical criteria change, regenerates the packet, and shows the
   SME the semantic diff before revised domain approval.
4. The engineer audits the graders, reviews the technical section, records technical approval, and
   obtains a fresh CI report tied to the revised digest.
5. Compare setup, review effort, corrections, and false blocks with the pair's existing tests plus
   ordinary pull-request review—not with having no evaluations.

## Record

- Setup and reviewer time, facilitator interventions, and misunderstood instructions.
- Corrections to expectations, controls, grader behavior, and any false blockers.
- The specific mistake, disagreement, or rework that the workflow prevented.
- Whether the report clearly distinguishes fresh execution from verification of saved evidence.
- Whether each pair voluntarily chooses EDD for a second eligible feature within four weeks.

## Release target

- A specialist reviews a real feature without reading code, corrects an expectation, and approves
  the revised domain criteria.
- An engineer receives fresh CI evidence tied to that revised approval and can explain its limits.
- At least one pair voluntarily uses EDD for a second feature; otherwise simplify around the parts
  they did value, especially skills and the review packet.

Failure to meet a target is a product finding. Revise the workflow or language and repeat the
affected tasks; do not coach participants into a passing result.
