# Contributing to Birdseye

Every change goes through a branch and a pull request (PR). Nobody pushes directly to `main`, so `main` always works.

## 1. Start from a Jira ticket

Every piece of work has a Jira ticket in the TA4 project. Move the ticket to **In Progress** when you start.

## 2. Create a branch

Get the latest `main`, then create a branch named after the ticket:

```bash
git checkout main
git pull
git checkout -b TA4-54-top-skills
```

**Branch naming:** `TA4-<number>-<short-description>`, lowercase, words separated by hyphens.

Examples:
- `TA4-24-clean-dataset`
- `TA4-62-comparison-chart`

## 3. Commit your work

Start every commit message with the Jira key so the commit shows up on the ticket:

```bash
git add .
git commit -m "TA4-54: Add top 15 skills calculation"
```

Keep commits small and focused. Before committing, run `git status` and check that no data files, `.env` files, or passwords are included.

## 4. Update the changelog

Add one line to `CHANGELOG.md` under `[Unreleased]`, in the heading that fits your change (Added, Changed, Fixed, Removed, Data, or Infrastructure):

```markdown
- TA4-54: Top 15 skills summary, showing the share of postings for each skill. (#3)
```

Add the PR number once you've opened the PR.

## 5. Open a pull request

```bash
git push -u origin TA4-54-top-skills
```

Then open a PR into `main` on GitHub.

- **Title:** start with the Jira key, e.g. `TA4-54: Top 15 skills summary`
- **Description:** what changed, how to test it, and a link to the Jira ticket

**PR checklist** (copy into your PR description):

```markdown
- [ ] Branch is named `TA4-<number>-<description>`
- [ ] PR title starts with the Jira key
- [ ] `pytest` passes locally
- [ ] README updated if setup or usage changed
- [ ] Line added to CHANGELOG.md under [Unreleased]
- [ ] No data files, secrets, or `.env` files included
```

## 6. Review and merge

- At least **one teammate other than the author** reviews and approves every PR.
- Reviewers check that the code runs, `pytest` passes, and the checklist is complete. Leave comments on anything unclear.
- The author fixes any requested changes and pushes to the same branch.
- After approval, the **author** merges the PR and deletes the branch.
- Move the Jira ticket to **Done** once its acceptance criteria are met.

If two PRs both edit `CHANGELOG.md` and Git reports a merge conflict, keep both lines.

## Data and secrets

- Never commit datasets, database files, or credentials. `.gitignore` excludes the common cases, but always check `git status` before committing.
- If configuration is ever needed, put placeholder values in `.env.example` and real values in your own local `.env` file, which is ignored.

## Questions

Ask in the team channel or tag the ticket owner in Jira.
