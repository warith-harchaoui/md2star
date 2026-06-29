# Bibliography fixture

This fixture exercises the `--bib` / `--bibliography-name` path. The
referenced citation key (`pearl2009`) is defined in
`tests/fixtures/refs.bib`.

## What we cite

We rely on the causal-inference framework of @pearl2009 throughout
this work. See also the foundational treatment in [@pearl2000].

(Both `pearl2009` and `pearl2000` resolve via Pandoc's citeproc
against `refs.bib`. When `--bib` is passed, an automatic
"Bibliography" / `--bibliography-name` heading is appended at the
end.)
