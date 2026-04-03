# Contributing Guide

This project uses a branch + pull request workflow.

## Team Rules

1. `main` must stay stable and deployable.
2. Do not push feature work directly to `main`.
3. Every change goes through a pull request (PR).
4. Keep commits small and messages clear.

## One-Time Local Setup

Run this once after cloning:

```bash
./scripts/setup-git-workflow.sh https://github.com/mahdi-mortada/snuggle-buddy-build.git
```

This configures local Git hooks and sets `origin` if missing.

## Daily Start (Always Sync First)

```bash
git checkout main
git pull origin main
```

Then update your branch:

```bash
git checkout your-branch
git merge main
```

If your branch does not exist yet:

```bash
git checkout -b feature-short-name
```

## Development Flow

```bash
git add .
git commit -m "Fix login bug when password is empty"
git push origin your-branch
```

Then open a PR from `your-branch` into `main`.

## Pull Request Checklist

Before requesting review, confirm:

1. Branch is up to date with `main`.
2. Scope is focused (no unrelated changes).
3. Tests were run locally when applicable.
4. Commit messages are descriptive.
5. PR description explains what changed and why.

## Merge Conflict Flow

When Git reports conflicts:

1. Open conflicting files and keep the correct lines.
2. Remove conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
3. Stage and commit the resolution:

```bash
git add .
git commit -m "Resolve merge conflict in <file>"
```

## Commit Message Examples

Good:

- `Fix login bug when password is empty`
- `Add validation for incident severity field`
- `Refactor navbar state handling`

Avoid:

- `update`
- `fix stuff`
- `misc changes`

## Stay In Sync During Active Collaboration

Use these regularly while teammates are working:

```bash
git fetch origin
git checkout main
git pull origin main
git checkout your-branch
git merge main
```

## Optional Project Management

- Use GitHub Issues for tasks and bugs.
- Use GitHub Projects for sprint/workflow tracking.
- Use code reviews to catch issues early.

## One-Page Workflow

1. Pull latest `main`.
2. Create or update your branch.
3. Code and commit in small chunks.
4. Push your branch.
5. Open PR.
6. Get review and merge.
