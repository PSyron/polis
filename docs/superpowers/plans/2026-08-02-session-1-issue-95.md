# Session 1 Prompt: Runtime Hardening (#95)

Copy the text below into a new Codex session.

```text
You are working as the solution architect and developer in the repository
`/Users/syron/Developer/polis`.

Lead the product workstream for GitHub issue #95: "Track generative Unicode,
offset, and correction invariant hardening".

Initial state:
- `main` should contain completed issues #120 and #84.
- The expected commit after #84 is
  `8d2491127ea452f1f7fef2d2b177f015c0fd29b9`.
- Another session is working on #119 in parallel.
- Do not modify the scope of #119, sentence safety corpora, or optional model
  qualification.

Working rules:
1. Read all of `AGENTS.md` and `PROMPT.md`.
2. Inspect the current state of issue #95, its dependencies and comments, and
   verify the current state of `main`.
3. Update local `main` from the remote repository.
4. Use the relevant Superpowers skills: brainstorming, writing-plans,
   using-git-worktrees, test-driven-development, subagent-driven-development,
   requesting-code-review, and verification-before-completion.
5. #95 is a tracking issue. Do not implement it as one large change.
6. Design atomic child issues covering every acceptance criterion in #95.
   Check whether any already exist before creating new ones.
7. Record dependencies and execution order. Every child must have an independent
   scope, acceptance criteria, required tests, and Definition of Done.
8. After completing the decomposition, select the first unblocked child issue
   and implement only that issue.
9. Create an isolated worktree and a `codex/` branch associated with the child
   issue number.
10. Use TDD: first add a test demonstrating the missing invariant or safeguard,
    then write the smallest implementation needed to pass it.
11. Preserve public contracts, offline privacy, Unicode half-open offsets
    `[start, end)`, fail-closed correction policy, and existing linguistic
    behavior.
12. Generated data must be synthetic, deterministic, time-bounded, and
    reproducible using a seed. CI failures must not print private analyzed text.
13. Do not add abstractions without a current consumer. Do not run model or
    holdout evaluations.
14. Use subagents in isolated worktrees for independent tasks when they will not
    edit the same files.
15. Review the result against the issue and plan. Resolve every important review
    finding.
16. Run all required verification: relevant pytest tests, the complete fast test
    suite, Ruff lint, Ruff format check, and mypy.
17. One child issue equals one focused commit and one separate PR. Do not add
    co-authors, automation attribution, or tool signatures.
18. Do not merge until CI is green and every child-issue acceptance criterion is
    demonstrated. If permissions allow and no blocker remains, take the first
    child issue through PR, CI, merge, and issue closure.
19. Update #95 only with evidence from the completed child. Do not close #95
    until every child is complete.
20. After the assigned session work is fully integrated and its GitHub state is
    verified, delete
    `docs/superpowers/plans/2026-08-02-session-1-issue-95.md` in the final focused
    commit or PR before declaring the session complete. Do not delete the prompt
    used by the parallel #119 session.

Work autonomously. Stop only for a genuine conflict between decision sources,
an irreversible risk, or a required product-owner decision.

The final report must include:
- the #95 child-issue decomposition and dependencies;
- the implemented child issue number;
- changed files;
- commit and PR;
- tests run and CI results;
- merge and issue status;
- known limitations;
- the next unblocked child issue;
- confirmation that this session prompt was removed from `main`.
```
