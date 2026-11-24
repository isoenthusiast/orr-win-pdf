# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private reporting instead — **Security ▸ Report a vulnerability**
on this repository, or go straight to
<https://github.com/isoenthusiast/orr-win-pdf/security/advisories/new>.

That opens a private thread visible only to you and the maintainer, so you
can describe the problem, share a proof of concept, and agree on a fix
before anything is public. You should get an acknowledgement within a few
days. Fixes land as ordinary commits on `main`, and the advisory is
published once people have had a reasonable chance to pick them up.

## What counts as a vulnerability

- a crash or code execution triggered by opening a crafted PDF
- a bug that lets one PDF write outside the file you asked it to
- anything that reads files or data from the user's machine that it should not
- a way to make the app run a command of an attacker's choosing

## What does not count

- the app reading the PDF you opened — that is the whole job
- anything that already requires the user to run hostile code as themselves
- bugs in MuPDF or Pillow upstream, which need fixing in those projects
  (report them to Artifex and to the Pillow project, not here)

## Supported versions

| version | supported |
|---|---|
| `main` | yes |

There is no commercial support and no release cadence; fixes land on `main`
and anyone who builds from source gets them immediately.

## Note on the licence

This project is free software under the AGPL-3.0. There is no warranty, and
the maintainer accepts no liability for damage arising from its use.
