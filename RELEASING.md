# Releasing

statgate publishes to PyPI through [trusted publishing](https://docs.pypi.org/trusted-publishers/),
so no API tokens are stored anywhere.

## One-time setup (maintainer)

1. Sign in at https://pypi.org (create the account if needed, with 2FA).
2. Go to https://pypi.org/manage/account/publishing/ and add a
   **pending publisher** with exactly these values:
   - PyPI project name: `statgate`
   - Owner: `yashchimata`
   - Repository name: `statgate`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. That is all. The first successful run of the Release workflow claims
   the `statgate` name and publishes.

## Cutting a release

1. Update the version in `pyproject.toml` and `src/statgate/__about__.py`
   (keep them identical) and add a section to `CHANGELOG.md`.
2. Commit, push, and confirm CI is green.
3. Tag and publish a GitHub release:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file notes.md
   ```

4. Publishing the GitHub release triggers `.github/workflows/release.yml`,
   which builds the sdist and wheel and uploads them to PyPI. The
   workflow can also be started manually from the Actions tab
   (workflow_dispatch), or re-run if the PyPI side was not ready yet.
5. Verify with `pip install statgate==X.Y.Z` in a fresh environment.

## Regenerating README screenshots

```bash
python scripts/render_assets.py
```

The SVGs in `assets/` are produced from real output on `examples/`, so
regenerate them whenever report rendering changes.
