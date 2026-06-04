# Conventions (caveman spec + file formats)

Stated once here. All .agent/ files conform. Don't repeat in each file header — truth has one home.

## Caveman style (every .agent/ file except this prompt's prose & human README)
- Fragments not sentences. Drop articles/copulas when meaning survives.
- Symbols ok: → = vs & w/ b/c ≤ ≥ ⚠. One fact per line. Lists/tables > paragraphs.
- No preamble, no filler, no restating the master prompt.
- KEEP the WHY, just compress it. `set_last_result global → cross-session leak` not a paragraph.
- Content nouns + identifiers VERBATIM: paths, fn names, table/col names, endpoints, term names.
  Never compress these — ambiguity worse than length.
- Parseable cold by a different provider's agent. Caveman, never cryptic.

## Frontmatter (every code-tied note: modules/, and any note w/ `covers`)
```yaml
---
covers: [backend/agent.py]        # code paths the note describes
synced: <commit-sha>              # cli mode: commit note was true as of (short sha ok)
mode: explore                     # work mode that last wrote it: explore|build|review|plan
---
```
- Policy notes (security.md, guidelines.md, conventions.md) = NO frontmatter, NOT drift-checked.
- notes.md, integrations.md, gaps.md, architecture.md, index.md, log.md = no per-file `covers`
  (architecture is coarse-global; gaps/notes reference paths inline). Drift-check only modules/.
- Backend here = MODE=cli. `synced` = git short-sha. On backend switch /check recomputes format.

## log.md line shape (append-only, one event/line)
```
## [YYYY-MM-DD] <type> | <summary> (<ref>)
```
type ∈ decision|howto|note|gaps|build|check|scaffold. ref optional (decisions/0007, howto/slug).
Timeline: `grep "^## \[" .agent/log.md | tail`.

## index.md line shape
```
- [path](path) — 1-line what-it-covers
```

## gaps.md line shape
```
- [SEV] <area> | <weakness> → <why it matters> | status:<open|mitigated|resolved>
```
SEV ∈ 🔴high|🟠med|🟡low.

## tasks/T-NNN.md (only if plan.md added later)
frontmatter: status ∈ todo|doing|done|blocked|deferred · owner · blocked_by · updated.
cli claim = set owner+status:doing, commit that file alone before working. Double-claim → git conflict.

## Module note shape (coarse, type-(a), drift slow)
covers + 1-line role · entry points · key fns/lines · state owned · neighbors (in/out) ·
4 lenses (state/feedback/blast-radius/timing) when they bite · WHY/surprises → link [[notes]].
