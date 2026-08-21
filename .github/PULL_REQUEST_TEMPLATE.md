<!-- Thanks for contributing! Small PRs are absolutely welcome. -->

## What & why

<!-- What does this change, and what problem does it solve?
     Link the issue if one exists: Fixes #123 -->

## How it was verified

<!-- Tests run, databases tried, before/after output.
     Bug fixes should come with a regression test that fails on the old code
     (see CONTRIBUTING.md). -->

## Checklist

- [ ] `pytest` is green locally
- [ ] Bug fix → includes a regression test; feature → includes tests
- [ ] No real sensitive data in code, tests, or examples
- [ ] User-facing change → noted under `[Unreleased]` in CHANGELOG.md
- [ ] Python 3.9-compatible (no `match`, no `X | Y` unions in runtime code)
