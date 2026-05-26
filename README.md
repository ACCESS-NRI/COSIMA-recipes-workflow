# ACCESS-NRI MED COSIMA-recipes Workflow

ACCESS-NRI maintenance workflow for testing COSIMA Recipes on NCI Gadi.

## Stage 1 smoke test

The active workflow, `.github/workflows/cosima-recipe.yml`, is manually dispatched and runs one manifest-listed notebook on Gadi via PBS:

- `02-Appetisers/Barotropic_Streamfunction.ipynb`

The workflow:

1. Reads `.github/configs/cosima-smoke.json` and validates the requested notebook path.
2. SSHes to Gadi using repository secrets.
3. Creates a predictable run directory under `${GADI_SCRIPTS_DIR}/cosima-recipes-ci/runs/<github-run>-<attempt>-<notebook>/` unless `gadi_work_dir` is supplied at dispatch time.
4. Clones/fetches `COSIMA/cosima-recipes`, checks out the requested ref, and validates that the notebook exists.
5. Writes and submits a non-blocking PBS script using the configured `conda_module` and `module_base_path`.
6. Polls for a result JSON file and writes the pass/fail outcome to the GitHub Actions summary.

Required GitHub secrets:

- `GADI_USER`
- `GADI_KEY`
- `GADI_KEY_PASSPHRASE` if the key is encrypted
- `GADI_SCRIPTS_DIR` unless `gadi_work_dir` is supplied manually

The Stage 1 workflow intentionally tests only one notebook. Expansion to a broader smoke suite should happen after this path proves reliable on Gadi.
