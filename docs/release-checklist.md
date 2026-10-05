# Public release checklist

The implementation is organized as a portable Agent Skill plus a Codex plugin wrapper. Complete these maintainer-owned decisions before calling the GitHub release final.

## Required decisions

- [x] Use `liangchen0333/project-recall` as the canonical repository.
- [x] Use the MIT License, copyright 2026 liangchen0333.
- [x] Use `liangchen0333` as the maintainer identity in plugin metadata.
- [x] Publish both: the repository root is a portable Codex plugin, and `skills/project-recall` is independently installable.
- [ ] Decide whether to include branded marketplace icons; the skill works without them.

## Verification

- [ ] Run `python -m unittest discover -s tests -v` on Windows, macOS, and Linux.
- [ ] Evaluate every case in `evals/trigger-cases.json` in the target host.
- [ ] Confirm a bare `继续` / `continue` does not trigger recall.
- [ ] Confirm selecting the skill shows the clarity picker without reading state.
- [ ] Confirm every recap stops before project execution.
- [ ] Confirm the hook exits quietly outside tracked projects.
- [ ] Confirm dashboard mode is read-only.
- [ ] Review the packaged hook before approving it in Codex.

## Release hygiene

- [ ] Replace release-candidate language in the README if appropriate.
- [ ] Record changes in `CHANGELOG.md`.
- [ ] Create a signed or annotated version tag matching `plugin.json`.
- [ ] Publish checksums or immutable release archives if distributing outside GitHub.
