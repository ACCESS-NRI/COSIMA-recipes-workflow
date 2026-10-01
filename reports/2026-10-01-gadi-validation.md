# Gadi validation: 1 October 2026

The `codex/fix-workflow` branch was exercised directly on Gadi with project
`tm70` against COSIMA Recipes commit `6278c5bf45924f756de9c00058eecdea0514d7ad`.
All 38 discovered notebooks were submitted for each of the six newest
versioned `analysis3` modules. The corrected Barotropic Streamfunction smoke
test passed on `analysis3-26.10`. The dashboard data checked into this branch
contains the six full-suite summaries.

| Module | Passed | Failed | Missing result |
| --- | ---: | ---: | ---: |
| `analysis3-26.05` | 13 | 25 | 0 |
| `analysis3-26.06` | 26 | 12 | 0 |
| `analysis3-26.07` | 27 | 11 | 0 |
| `analysis3-26.08` | 27 | 11 | 0 |
| `analysis3-26.09` | 28 | 9 | 1 |
| `analysis3-26.10` | 26 | 12 | 0 |

Eleven notebooks passed in all six modules. Ten had no passes; the remaining
17 passed on some versions and failed on others. `analysis3-26.05` had
14 `ESMDataSourceError` failures, many on notebooks that passed in newer modules.
The differences need investigation in the Recipes repository or environment
catalogues before they are treated as reproducible regressions.

Several failures are independent of the workflow. For example,
`Compare_SSH_model_obs.ipynb` refers to
`/g/data/ua8/CMEMS_SeaLevel/timeseries/*.nc`, which did not exist on Gadi
during this run. Other recurring errors include an existing `movie_sst.gif`,
an ambiguous `longitude` coordinate, and an unavailable `%%timeit` magic.
Some notebooks write to shared paths under `/scratch/tm70/rb5533`, so concurrent
jobs may also affect their outcomes.

Live PBS testing exposed two workflow resource issues that were fixed on this
branch: Gadi preloaded another `analysis3` version, and the 100 MB default
jobfs killed notebook jobs before they could write a result. PBS scripts now
purge preloaded modules and request 100 GB jobfs. Eight terminated jobs were
retried with that request, plus one retry after a transient Singularity mount
error. The `analysis3-26.09` run of
`Heaving_Water_mass_transformation_decomposition.ipynb` still exceeded 100 GB
jobfs (about 117 GB used) and is recorded as a missing result with its PBS
termination reason. It needs a larger notebook-specific allocation or less
temporary disk use if this recipe is expected to pass.

The GitHub Actions schedule, artifact transfer, and Pages deployment have not
yet run end to end. They require the branch to be merged into `main`; the
manual Gadi run and local dashboard build validated the PBS execution,
summary generation, and six-version selector data.
