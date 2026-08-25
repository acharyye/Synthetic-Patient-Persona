"""Refuse to rewrite anything the remote already carries.

    python scripts/check_release_freeze.py --tag v0.4
    python scripts/check_release_freeze.py --commit HEAD
    python scripts/check_release_freeze.py --tag v0.5 --commit HEAD   # both

Exit 0 means the target is local-only and safe to amend or re-cut. Any other exit
means it is published and the freeze applies: correct it with a NOTE beside the
artifact, never by rewriting the artifact.

Why this exists. On 2026-08-25 the v0.4 release notes were found to assert a
mechanism that the segment read had just shown describes 1 case in 18. The
release was believed to be unpushed, so an amend-and-re-tag was authorised and
performed — on a tag and three commits that were already on the remote. Nothing
was force-pushed and the local rewrite was reverted, but the only thing standing
between "near miss" and "rewrote published history" was somebody happening to
read an `ahead 4, behind 3` line.

Two operators, one unverified premise, and a rule that lived only in prose. So the
rule stops living in prose. Every path that rewrites a release runs this first.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def _git(*args: str) -> tuple[int, str]:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    return result.returncode, result.stdout.strip()


def tag_is_published(tag: str, remote: str) -> bool:
    code, out = _git("ls-remote", "--tags", remote, f"refs/tags/{tag}")
    if code != 0:
        raise SystemExit(f"cannot reach {remote!r}: refusing to assume it is safe")
    return bool(out.strip())


def commit_is_published(rev: str, remote: str) -> bool:
    """Reachable from any remote-tracking branch of `remote`.

    Deliberately asks git rather than the network: a commit is published if a
    fetched remote ref contains it. Run `git fetch` first if the answer matters,
    which the CLI does.
    """
    code, sha = _git("rev-parse", "--verify", f"{rev}^{{commit}}")
    if code != 0:
        raise SystemExit(f"not a commit: {rev!r}")
    code, out = _git("branch", "--remotes", "--contains", sha, f"{remote}/*")
    return bool(out.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="tag about to be deleted or moved")
    parser.add_argument("--commit", help="commit about to be amended or rebased")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--no-fetch", action="store_true",
                        help="skip the fetch; only for tests with no network")
    args = parser.parse_args(argv)

    if not (args.tag or args.commit):
        parser.error("name a --tag or a --commit")

    if not args.no_fetch:
        # A stale remote-tracking ref is exactly how this failed the first time.
        _git("fetch", args.remote, "--tags", "--quiet")

    published = []
    if args.tag and tag_is_published(args.tag, args.remote):
        published.append(f"tag {args.tag}")
    if args.commit and commit_is_published(args.commit, args.remote):
        published.append(f"commit {args.commit}")

    if published:
        print(f"REFUSED: {' and '.join(published)} already on {args.remote}.")
        print("The freeze applies at publication. Correct it with a dated NOTE "
              "beside the artifact — see RELEASE.NOTE.md for the shape — and do "
              "not rewrite what a reader may already hold.")
        return 2

    print(f"clear: nothing named is on {args.remote}; amending is local-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
