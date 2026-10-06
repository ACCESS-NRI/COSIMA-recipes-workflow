# COSIMA Recipes CI and dashboard

An ACCESS-NRI alpha prototype that runs [COSIMA Recipes](https://github.com/COSIMA/cosima-recipes)
notebooks on NCI Gadi and publishes the results in a
[dashboard](https://access-nri.github.io/COSIMA-recipes-workflow/). It is intended
to make recipe failures and differences between `analysis3` releases easier to
spot and discuss.

Every Monday at 08:15 Brisbane time, the all-recipes workflow discovers the six
newest versioned `analysis3` modules available on Gadi and tests every notebook
in the four recipe directories listed below. The selection updates automatically
as new modules appear. The workflow can also be run manually. An initial direct
Gadi run tested 38 notebooks across six versions; see the
[validation report](reports/2026-10-01-gadi-validation.md) for its results and
limits.

Both workflows execute COSIMA Recipes from the pinned commit
[`6278c5bf45924f756de9c00058eecdea0514d7ad`](https://github.com/COSIMA/cosima-recipes/commit/6278c5bf45924f756de9c00058eecdea0514d7ad),
which was used for that Gadi validation. Manual runs use the same commit and
cannot select a branch or tag. To test a newer Recipes version, review the
notebook changes and update `recipes_ref` in both
[all-recipes](.github/configs/cosima-all-recipes.json) and
[smoke-test](.github/configs/cosima-smoke.json) configs in a workflow repository
PR. New commits to COSIMA Recipes `main` will not enter scheduled tests until
the pin is deliberately updated.

## Dashboard

Open the [COSIMA Recipes dashboard](https://access-nri.github.io/COSIMA-recipes-workflow/)
to inspect results:

- Choose an `analysis3` environment to see its results. The selector shows the
  six versions chosen for the latest imported run.
- Use the search box and Overview, Recipe Cards, or Table view to find a
  notebook. The Overview shows all discovered notebooks, not just a sample.
- Failed, timed-out, and missing results show a short error or PBS termination
  reason when one was captured. The Table view also shows the log path on Gadi.
- Select a recipe card to open the source notebook in COSIMA Recipes at the
  tested commit when that information is available. Use Run Detail to check
  the run's resources and result counts.

The dashboard is read-only. It displays brief failure reasons, but it does not
host the full execution logs or executed notebooks. For more detail, use the
path in the Table view to read the log on Gadi. Run directories also contain
result JSON and any executed notebooks that were produced. A failed status can
reflect a notebook, input data, environment, resource limit, or infrastructure
problem, so check the error before treating it as a recipe regression.

The dashboard deployment runs after an all-recipes workflow finishes and imports
its available per-version summary artifacts, including failed runs. A selected
version without a summary is shown as *Not run*. Manual and push-triggered
deployments use the latest completed run with unexpired summary artifacts.
Until a GitHub Actions all-recipes run produces artifacts, the checked-in data
shows the [1 October 2026 Gadi validation](reports/2026-10-01-gadi-validation.md).

## Workflows

### Smoke test

The [smoke-test workflow](.github/workflows/cosima-recipe.yml) can be started
manually from the GitHub Actions tab. By default it runs this notebook on Gadi
via PBS:

- `02-Easy-Recipes/Barotropic_Streamfunction.ipynb`

The workflow:

1. Reads `.github/configs/cosima-smoke.json` and validates the requested notebook path.
2. SSHes to Gadi using repository secrets.
3. Creates a predictable run directory under `${GADI_SCRIPTS_DIR}/cosima-recipes-ci/runs/<github-run>-<attempt>-<notebook>/` unless `gadi_work_dir` is supplied at dispatch time.
4. Clones/fetches `COSIMA/cosima-recipes`, verifies the checked-out commit matches the pinned SHA, and validates that the notebook exists.
5. Writes and submits a non-blocking PBS script using the configured `conda_module` and `module_base_path`.
6. Polls for a result JSON file and writes the pass/fail outcome to the GitHub Actions summary.

### All recipes

The [all-recipes workflow](.github/workflows/cosima-all-recipes.yml) runs every
Monday at 08:15 Australia/Brisbane time (Sunday 22:15 UTC). To run it sooner,
open **Actions → COSIMA All Recipes → Run workflow**. It tests the pinned
COSIMA Recipes commit on Gadi project `tm70` with the `XLarge`
resource profile. Each run selects the six newest `analysis3-YY.MM` modules;
new releases enter the next run and the oldest selected version drops out. It
discovers every `.ipynb` file under the roots configured in
[cosima-all-recipes.json](.github/configs/cosima-all-recipes.json):

- `01-Cooking-Tutorials`
- `02-Easy-Recipes`
- `03-Advanced-Recipes`
- `04-Regional-Specialties`

The workflow:

1. SSHes to Gadi, checks that the configured PBS project has service units, and selects the six newest `analysis3-YY.MM` modules available in the configured module directory.
2. Runs a separate GitHub Actions job for each version. Failures in one version do not cancel the others.
3. Plans and validates the Gadi/PBS settings from `.github/configs/cosima-all-recipes.json` and workflow inputs.
4. Creates a separate run directory under `${GADI_SCRIPTS_DIR}/cosima-recipes-ci/runs/<github-run>-<attempt>-analysis3-<version>/` for each version, unless `gadi_work_dir` is supplied at dispatch time.
5. Clones/fetches `COSIMA/cosima-recipes` and verifies the checked-out commit matches the pinned SHA.
6. Discovers all `.ipynb` files under the configured recipe roots and writes a tab-separated notebook manifest.
7. Submits one PBS job per notebook and version with 100 GB of job-local scratch (`jobfs`). Each job runs `jupyter nbconvert --execute`, writes a per-notebook log, executed notebook, and result JSON.
8. Polls for results or timeout, writes an aggregate summary JSON for each version, and fails that version's GitHub Actions job if a notebook failed, timed out, or did not produce a result.

Useful workflow inputs:

- `resource_profile`: `Medium` (4 CPUs, 18 GB), `Large` (7 CPUs, 32 GB),
  `XLarge` (14 CPUs, 63 GB; default), `XXLarge` (28 CPUs, 126 GB), or
  `XXLargeMem` (28 CPUs, 252 GB). All use the `normalbw` queue.
- `module_base_path`: Gadi directory containing the versioned modules.
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
