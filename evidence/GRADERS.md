# Grader versioning

- **v1** (through commit 3ecd41e): keyword/word-boundary matchers. Blind spot: an
  answer naming the right fact AND a wrong alternative (e.g. "CRON_TZ or
  SCHEDULER_TZ, UTC") passed.
- **v2** (2026-11-08): same required patterns plus contradiction rejection
  (wrong alternative numbers/ids/variables fail unless explicitly negated).
  Shipped controls: `python -m bench.controls` - 36 cases, all behave.

## Re-scored history (no silent relabeling)

`evidence/matrix4-20261108.jsonl` (56 runs, executed and recorded under v1) was
re-scored offline with v2 on 2026-11-08: **0 of 56 outcomes flip**. The file is
kept byte-identical to its v1 recording.

`evidence/matrix8-20261108.jsonl` (112 runs) was executed under v2; its recorded
outcomes are v2 outcomes. This is the current reference matrix.
