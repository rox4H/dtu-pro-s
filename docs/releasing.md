# Releasing

This project publishes the Python distribution to PyPI through GitHub Actions and PyPI Trusted Publishing (OIDC). No long-lived PyPI API token is stored in GitHub.

The JavaScript client is tested and attached to GitHub Releases as an npm tarball. It is not published to the npm registry by this workflow.

## One-time PyPI setup

After the clean public repository has been created:

1. Keep the current repository private and rename it to `dtu-pro-s-private`. Create a new public repository named `dtu-pro-s` from a clean snapshot, with a single initial commit. Do not change the visibility of the historical repository.
2. On PyPI, open [Publishing settings](https://pypi.org/manage/account/publishing/).
3. Add a pending publisher with these exact values:
   - PyPI project name: `hoymiles-dtu-reader`
   - Owner: `rox4H`
   - Repository: `dtu-pro-s`
   - Workflow filename: `release.yml`
   - Environment: `pypi`
4. In GitHub, create the `pypi` environment under **Settings → Environments**.
5. Require an explicit reviewer for the `pypi` environment. Keep the publishing job restricted to the release workflow.

The first successful trusted publication creates the PyPI project if it does not already exist. See the [PyPI Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/) for details.

## Publish a release

1. Update `src/hoymiles_dtu_reader/__init__.py` and the changelog for the intended release.
2. Ensure the tag exactly matches the package version. For example, for version `2.0.0`:

   ```bash
   git tag -a v2.0.0 -m "Release v2.0.0"
   git push origin v2.0.0
   ```

3. GitHub Actions runs the test suite, builds the Python wheel and source distribution, validates them with Twine, and packs the JavaScript client.
4. After PyPI publication is approved and succeeds, the workflow creates a GitHub Release with the Python distributions and npm tarball attached.

The release workflow uses the `pypi` GitHub environment and OIDC permission only in the publishing job. The GitHub Release job receives `contents: write`; the build job has read-only repository permissions.

## Before the first public release

- Create the public repository from a clean snapshot rather than changing the existing private repository's visibility.
- Configure the PyPI Trusted Publisher against the final public repository name.
- Confirm the `hoymiles-dtu-reader` project name is available on PyPI before the first upload.
- Review the release artifacts and changelog before pushing the version tag.
