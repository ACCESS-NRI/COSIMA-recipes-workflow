# ACCESS-NRI MED COSIMA-recipes Workflow

ACCESS-NRI maintenance workflows for testing COSIMA Recipes on NCI Gadi.

## Workflows

### Smoke test

`.github/workflows/cosima-recipe.yml` is manually dispatched and runs one manifest-listed notebook on Gadi via PBS:

- `02-Easy-Recipes/Barotropic_Streamfunction.ipynb`

The workflow:

1. Reads `.github/configs/cosima-smoke.json` and validates the requested notebook path.
2. SSHes to Gadi using repository secrets.
3. Creates a predictable run directory under `${GADI_SCRIPTS_DIR}/cosima-recipes-ci/runs/<github-run>-<attempt>-<notebook>/` unless `gadi_work_dir` is supplied at dispatch time.
4. Clones/fetches `COSIMA/cosima-recipes`, checks out the requested ref, and validates that the notebook exists.
5. Writes and submits a non-blocking PBS script using the configured `conda_module` and `module_base_path`.
6. Polls for a result JSON file and writes the pass/fail outcome to the GitHub Actions summary.

### All recipes

`.github/workflows/cosima-all-recipes.yml` is manually dispatched and runs every notebook found under the COSIMA Recipes recipe roots configured in `.github/configs/cosima-all-recipes.json`:

- `01-Cooking-Tutorials`
- `02-Easy-Recipes`
- `03-Advanced-Recipes`
- `04-Regional-Specialties`

The workflow:

1. Plans and validates the Gadi/PBS settings from `.github/configs/cosima-all-recipes.json` and workflow inputs.
2. SSHes to Gadi using repository secrets.
3. Creates a run directory under `${GADI_SCRIPTS_DIR}/cosima-recipes-ci/runs/<github-run>-<attempt>-all-recipes/` unless `gadi_work_dir` is supplied at dispatch time.
4. Clones/fetches `COSIMA/cosima-recipes` and checks out the requested ref.
5. Discovers all `.ipynb` files under the configured recipe roots and writes a tab-separated notebook manifest.
6. Submits one PBS array job with one array task per notebook. Each task runs `jupyter nbconvert --execute`, writes a per-notebook log, executed notebook, and result JSON.
7. Polls until every notebook has a result JSON, then writes an aggregate summary JSON and fails the GitHub Actions job if any notebook failed, timed out, or did not produce a result.

Useful workflow inputs:

- `recipes_ref`: COSIMA Recipes branch, tag, or SHA to test.
- `poll_timeout_minutes`: how long GitHub Actions should wait for the full PBS array.
- `execute_timeout_seconds`: per-notebook `nbconvert` timeout.
- `gadi_work_dir`: optional override for the Gadi base run directory.

## Required GitHub secrets

- `GADI_USER`
- `GADI_KEY`
- `GADI_KEY_PASSPHRASE` if the key is encrypted
- `GADI_SCRIPTS_DIR` unless `gadi_work_dir` is supplied manually
