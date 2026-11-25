# GitHub Support request — purge dangling commits exposing a local path

Filed at <https://support.github.com/> via the portal: *Other support → General support
request → category "Other" →* the *Solution* page confirmed the request matched GitHub's
private-information-removal process, and the ticket was created from that page.

- **Subject:** `Purge dangling commits exposing a local path - orr-win-pdf`
- **From:** the account's GitHub address
- **Type of Issue:** `Errors, problems; plus API rate-limits, Actions workflow issues, migration to GitHub`
- **Body:** the exact text below (plain text, no attachment)

**Ticket: [#5055506](https://help.github.com/support/tickets) — status: Open, priority: Normal.**
Created 2026-11-25. Watch for GitHub's reply at the account's GitHub address; they may ask
for more detail before they will action the server-side cleanup.

## Status checks

| Checked (UTC) | `16adb4a4…` | `85e9e47a…` | Cached commit page | Ticket #5055506 |
|---|---|---|---|---|
| 2026-11-25 09:36 | HTTP 200 — still fetchable | HTTP 200 — still fetchable | HTTP 200 — path still rendered | Open, priority Normal, no reply yet |

**Result: nothing has changed yet.** Both commits are still fully reachable by direct SHA,
the exposed line is still served verbatim, and the rendered commit page still shows the path.
The file is still absent from `main` and still unreferenced by any branch, tag or pull request.

What was checked, and how to repeat it:

```powershell
$repo = 'isoenthusiast/orr-win-pdf'
# 1. Is the commit object still in GitHub's storage?
gh api "repos/$repo/commits/16adb4a46cccf00dc8648e2e9174c118eaaaca4f"
gh api "repos/$repo/commits/85e9e47a9ba1040752a5023326d0232ab660fcf0"
# 2. Is the exposed file still served, with the path still in it?
gh api "repos/$repo/contents/tools/_inspect_exe.ps1?ref=16adb4a46cccf00dc8648e2e9174c118eaaaca4f"
# 3. Is the cached HTML view of the commit still live?
Invoke-WebRequest -Uri "https://github.com/$repo/commit/16adb4a46cccf00dc8648e2e9174c118eaaaca4f" -UseBasicParsing
# 4. Did anything re-reference the commits in the meantime?
gh api "repos/$repo/commits/16adb4a46cccf00dc8648e2e9174c118eaaaca4f/branches-where-head"
gh api "repos/$repo/commits/16adb4a46cccf00dc8648e2e9174c118eaaaca4f/pulls"
# 5. The ticket itself: https://help.github.com/ticket/personal/0/5055506
```

The purge is complete when step 1 returns `404 Not Found` and step 3 no longer renders the
path. Until then the exposure is public, which is expected — the server-side garbage
collection and cached-view removal are GitHub's to perform, not something the client can do.

---

Request to permanently remove two dangling commits that expose personal information (a local
filesystem path including the Windows account name) in a public repository.

**Repository:** https://github.com/isoenthusiast/orr-win-pdf (public, owner: isoenthusiast)

**Please note:** I am NOT asking to delete the repository. The repository is healthy and should
stay exactly as it is. I am asking only for server-side garbage collection and cached-view
removal for the two commits below.

## The two commits that are still exposed

| SHA | Date (UTC) | Subject | Effect on `tools/_inspect_exe.ps1` |
|---|---|---|---|
| `16adb4a46cccf00dc8648e2e9174c118eaaaca4f` | 2026-11-25T03:14:46Z | Release 1.1.0 | adds it (contains the exposed path) |
| `85e9e47a9ba1040752a5023326d0232ab660fcf0` | 2026-11-25T03:16:53Z | Remove a scratch script | deletes it |

Both are still retrievable directly by SHA on GitHub's servers, for example:
`GET /repos/isoenthusiast/orr-win-pdf/commits/16adb4a46cccf00dc8648e2e9174c118eaaaca4f`

## What the exposed data is

Exactly one line of `tools/_inspect_exe.ps1` (line 2) discloses a local path in the form:

```
Set-Location 'C:\Users\<account name>\OneDrive\Documents\...'
```

That is the entire exposure: the Windows account name and the local folder structure of the
repository owner.

**No credentials, tokens, API keys, passwords, or other secrets are involved**, so there is
nothing for me to rotate or revoke. This is personal information only.

## Why this poses a security risk

The exposed value is the absolute path of the repository owner's personal Windows workstation.
It publishes two things:

1. the Windows account name of the account holder, and
2. the directory layout of that account's OneDrive tree, including the personal folder that
   contains this repository.

It is not a credential, so there is nothing to revoke. But while these two commits remain
fetchable by SHA, the information is permanently and publicly linkable to a named individual.
Combined with the public commit history of this repository, it removes the guesswork from an
attack aimed at that person: it supplies the account holder's OS username for username
enumeration and credential-stuffing, and it supplies the exact folder layout needed to write a
convincing targeted phishing or social-engineering pretext (for example, "a file in your
OneDrive/Documents folder needs your attention").

Removal is the only remedy available. I cannot delete this from the client side, because the
surviving copies live in GitHub's object storage and in its cached views of the commit pages.

## What I have already completed

1. Rewrote the repository history to remove `tools/_inspect_exe.ps1` entirely, and force-pushed
   the rewritten history to `main`. Branch protection was temporarily relaxed to allow the force
   push and restored immediately afterwards.
2. Verified that **no branch, tag, or pull request** references either commit:
   - `GET /repos/isoenthusiast/orr-win-pdf/commits/<sha>/branches-where-head` returns an empty
     list for both.
   - `GET /repos/isoenthusiast/orr-win-pdf/commits/<sha>/pulls` returns an empty list for both.
3. Verified the repository has **0 forks**, so no fork coordination is needed.

## Information requested by the "removing sensitive data" process

- **Number of affected pull requests: 0.** No pull request references either commit, so no
  pull-request dereferencing is required. The only pull requests in this repository are
  Dependabot dependency bumps (#1-#5), none of which touched this file.
- **First changed commit:** `16adb4a46cccf00dc8648e2e9174c118eaaaca4f` ("Release 1.1.0"), which was
  rewritten to `d05d6859e7ad59b69ff8e6c75c2aba1269f22e1e`. The follow-up commit
  `85e9e47a9ba1040752a5023326d0232ab660fcf0` was also rewritten away because it sat on top of
  the tainted commit.
- **Last commit whose SHA was unchanged by the rewrite:**
  `84ac4bd3bc9ca00ca86b5cec3e043aaee2b92eb9` ("Make drag and drop actually work, and give the
  icon real sizes").
- **LFS objects orphaned by the rewrite:** none. This repository does not use Git LFS.

## What I am asking for

1. Run a garbage collection on the server so `16adb4a46cccf00dc8648e2e9174c118eaaaca4f` and
   `85e9e47a9ba1040752a5023326d0232ab660fcf0` are expunged from storage.
2. Remove cached views so the two commits can no longer be fetched by direct SHA.
3. Let me know if any additional step is required on my side.

Thank you.

---

## Reference

- GitHub Docs — Removing sensitive data from a repository:
  <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository>
- GitHub Docs — GitHub Private Information Removal Policy:
  <https://docs.github.com/en/site-policy/content-removal-policies/github-private-information-removal-policy>
