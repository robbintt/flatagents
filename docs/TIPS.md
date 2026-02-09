# FlatAgents Tips

> These tips were established during v2 development and remain current.
> See `README.md` for the current two-machine architecture.

## 1) Output management first (avoid JSON + Jinja)
Design outputs for **routing reliability first**, not structured elegance.

- Default to `output.content` (plain text/markdown).
- Avoid agent `output:` schemas unless a strict downstream contract requires it.
- Keep section generation as prose; assemble sections later.

For routing decisions, require one token only:
- `PASS`
- `REPAIR`
- `FAIL`

Implementation guidance:
- Put the enum requirement prominently in prompts.
- Normalize in hooks (`strip`, `upper`, fallback mapping).
- Route only on normalized enum values.

Avoid output anti-patterns:
- No JSON extractor/fixer loops for normal pipeline control flow.
- No regex-based JSON recovery unless absolutely unavoidable.
- No Jinja-heavy multi-layer prompt/output plumbing.
- No fragile templated JSON strings.

Preferred pattern:
- Hooks precompute clean input strings/fragments.
- Agents write plain section text.
- Final assembly is straightforward concatenation/ordering.
- Keep parsing surface area to near-zero (none, or enum normalization only).

## 2) Other implementation reliability notes
### FlatMachines action-hook safety
Action hook return values replace context.
- Always mutate + return the **full context**.
- Never return partial dicts from action hooks.

This avoids silent context loss and accidental judge/repair loops.

### Quick checklist before adding an agent/state
- Can this output stay plain text?
- Can routing use `PASS|REPAIR|FAIL` instead of JSON?
- Can hook normalization remove parsing fragility?
- Can Jinja/template logic be replaced by hook-prepared fields?
- Is there any parser here we can delete?
