# ACCESS-NRI MED COSIMA-recipes Workflow

ACCESS-NRI maintenance workflows for testing COSIMA Recipes on NCI Gadi.


## Dashboard

A GitHub Pages static dashboard is available at:

- <https://access-nri.github.io/COSIMA-recipes-workflow/>

Before the first run, the dashboard uses the legacy COSIMA all-recipes manifest.
After a run, it uses the notebook paths discovered on Gadi and the run summary
JSON, including failed and missing results. It shows per-recipe status, inferred recipe
style/category, an `analysis3` environment selector, and switchable overview,
cards, table, and run-detail views.

The dashboard deployment workflow runs when an all-recipes workflow completes.
It downloads the run's six version-specific summary artifacts, including failed
jobs, and its selected-version artifact. The environment selector shows the six
modules selected for that run; a version without a summary is shown as not run.
Manual and push-triggered deployments use the latest completed run with an
unexpired summary artifact.

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

`.github/workflows/cosima-all-recipes.yml` runs every Monday at 08:15
Australia/Brisbane time (Sunday 22:15 UTC), and can also be dispatched manually.
At the start of each run it discovers the six newest versioned `analysis3` modules
on Gadi. New releases enter the next run automatically and the oldest selected
version drops out. It tests every notebook found under the COSIMA Recipes recipe
roots configured in `.github/configs/cosima-all-recipes.json`:

- `01-Cooking-Tutorials`
- `02-Easy-Recipes`
- `03-Advanced-Recipes`
- `04-Regional-Specialties`

The workflow:

1. SSHes to Gadi, checks that the configured PBS project has service units, and selects the six newest `analysis3-YY.MM` modules available in the configured module directory.
2. Runs a separate GitHub Actions job for each version. Failures in one version do not cancel the others.
3. Plans and validates the Gadi/PBS settings from `.github/configs/cosima-all-recipes.json` and workflow inputs.
4. Creates a separate run directory under `${GADI_SCRIPTS_DIR}/cosima-recipes-ci/runs/<github-run>-<attempt>-analysis3-<version>/` for each version, unless `gadi_work_dir` is supplied at dispatch time.
5. Clones/fetches `COSIMA/cosima-recipes` and checks out the requested ref.
6. Discovers all `.ipynb` files under the configured recipe roots and writes a tab-separated notebook manifest.
7. Submits one PBS job per notebook and version with 100 GB of job-local scratch (`jobfs`). Each job runs `jupyter nbconvert --execute`, writes a per-notebook log, executed notebook, and result JSON.
8. Polls until every notebook has a result JSON, then writes an aggregate summary JSON for that version and fails its GitHub Actions job if any notebook failed, timed out, or did not produce a result.

Useful workflow inputs:

- `recipes_ref`: COSIMA Recipes branch, tag, or SHA to test.
- `resource_profile`: one of `Medium`, `Large`, `XLarge`, `XXLarge`, or `XXLargeMem`.
- all profiles run on `normalbw` with fixed CPU/memory presets: `Medium` (4 CPUs, 18GB), `Large` (7 CPUs, 32GB), `XLarge` (14 CPUs, 63GB), `XXLarge` (28 CPUs, 126GB), `XXLargeMem` (28 CPUs, 252GB).
- default profile is `XLarge`.
- `poll_timeout_minutes`: how long GitHub Actions should wait for all submitted PBS jobs.
- `execute_timeout_seconds`: per-notebook `nbconvert` timeout.
- `gadi_work_dir`: optional override for the Gadi base run directory.

The dashboard Run Detail view includes the resource profile, queue, CPU count,
memory, jobfs, and walltime used by each imported all-recipes run summary.

## Required GitHub secrets

- `GADI_USER`
- `GADI_KEY`
- `GADI_KEY_PASSPHRASE` if the key is encrypted
- `GADI_SCRIPTS_DIR` unless `gadi_work_dir` is supplied manually
