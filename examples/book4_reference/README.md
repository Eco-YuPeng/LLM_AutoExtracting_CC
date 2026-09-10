# Reference example: Robertson et al. (2000)

Read-only reference — learn the target output shape here, don't modify
this folder. New workflows go in `workflows/<project_name>/`.

## Why this paper

This paper was already fully verified by hand in a prior session
(Book4.xlsx year-extraction pass), so its target row uses real,
already-confirmed data rather than a fabricated example — consistent
with the project's no-fabrication rule.

**Robertson, G.P., Paul, E.A., Harwood, R.R. (2000).** "Greenhouse
Gases in Intensive Agriculture: Contributions of Individual Gases to
the Radiative Forcing of the Atmosphere." *Science* 289(5486), 1922-1925.

KBS LTER site, Michigan. The paper states verbatim: *"From 1991 to 1999
we measured gas fluxes..."* — this is why `year` below is a range and
its confidence is `high`: the value is a direct quote, not an inference.

## What this example shows

The pipeline does not have this PDF available in this environment, so
this folder documents the TARGET SHAPE a real run should produce — not
a runnable script pretending to have processed the file. When you have
the actual PDF, follow AGENTS.md's Core Steps and confirm your output
matches this shape (same columns, same confidence-tagging convention).

`expected_output.csv` in this folder has one row, populated only with
the fields that are genuinely known and verified for this paper (Block 1
core fields + confidence/source columns). Every Block 2 (yield/GHG/SOC/
nitrogen) field is left blank on purpose — Robertson et al. (2000)
reports cumulative global-warming-potential figures across gas types in
a form that does not map cleanly onto this schema's cc/control mean-SD
structure, and re-deriving those numbers here would risk misrepresenting
what the paper actually reported. A real extraction pass should fill
Block 2 only from a careful read of the source text, not by copying this
placeholder gap.

## How to reproduce this row for real

```bash
python scripts/check_pdf.py path/to/robertson_2000.pdf
```

Then follow AGENTS.md steps 2-12, using this row as the shape to match.
