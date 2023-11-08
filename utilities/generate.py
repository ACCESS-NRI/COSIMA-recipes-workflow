"""Generate PBS run scripts to run every recipe."""
import os
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader



dir_recipes = {"access_om2": Path('./cosima-recipes/ACCESS-OM2-GMD-Paper-Figs'),
               "contributed": Path('./cosima-recipes/ContributedExamples'),
               "documented": Path('./cosima-recipes/DocumentedExamples'),
               "tutorials": Path('./cosima-recipes/Tutorials')}

# Name of the conda environment
env = 'conda/access-med'
# Mail notifications when a submitted job fails or finishes
mail = False
submit = False
# Name of the NCI account in which the job will be billed
account = 'iq82'  # Select a compute project to be billed
# Name of the directory in which the job outputs files) are saved.
# The outputs will be saved in /home/user/<outputs>
outputs = '/g/data/kj13/admin/COSIMA-recipes/logs'
# Default Levante computing partition used
nci_queue = 'copyq'
# Default amount of memory used
memory = '64GB'
# Default walltime
walltime = '04:00:00'

# List of recipes that require non-default SLURM options set above
SPECIAL_RECIPES = {}

# These recipes either use CMIP3 input data
# and recipes where tasks require the full compute node memory.
ONE_TASK_RECIPES = []

    
# Fill the list with the names of the recipes to be excluded
exclude = []

def generate_submit():
    """Generate and submit scripts."""

    Path("./jobs").mkdir(parents=True, exist_ok=True)
    for key, val in dir_recipes.items():
        for recipe in Path(val).rglob('*.ipynb'):
            filename = f'launch_{recipe.stem}.pbs'
            filename = filename.replace(" ", "_")
            if recipe.stem in exclude:
                continue
            with open(f'jobs/{filename}', 'w', encoding='utf-8') as file:
                file.write('#!/bin/bash -l \n')
                file.write('#PBS -S /bin/bash\n')
                file.write(f'#PBS -P {account}\n')
                file.write('#PBS -l storage=gdata/kj13+gdata/fs38+gdata/oi10+gdata/rr3+gdata/xp65+gdata/al33+gdata/rt52+gdata/zz93+gdata/cb20\n')
                file.write(f'#PBS -N {recipe.stem}\n')
                file.write('#PBS -W block=true\n')
                file.write('#PBS -W umask=037\n')
                file.write('#PBS -l wd\n')
                file.write(
                    f'#PBS -o {outputs}/{recipe.stem}.out\n'
                )
                file.write(
                    f'#PBS -e {outputs}/{recipe.stem}.err\n'
                )
                if not SPECIAL_RECIPES.get(recipe.stem, None):
                    # continue
                    file.write(f'#PBS -q {nci_queue}\n')
                    file.write(f'#PBS -l walltime={walltime}\n')
                    file.write(f'#PBS -l mem={memory}\n')
                    file.write('#PBS -l ncpus=1\n')
                else:
                    if 'nci_queue' in SPECIAL_RECIPES[recipe.stem]:
                        file.write(SPECIAL_RECIPES[recipe.stem]['nci_queue'])
                    else:
                        file.write(f'#PBS -q {nci_queue}\n')
                    # Time requirements
                    # Special time requirements
                    if 'walltime' in SPECIAL_RECIPES[recipe.stem]:
                        file.write(SPECIAL_RECIPES[recipe.stem]['walltime'])
                    # Default
                    else:
                        file.write(f'#PBS -l walltime={walltime}\n')
                    # Special memory requirements
                    if 'memory' in SPECIAL_RECIPES[recipe.stem]:
                        file.write(SPECIAL_RECIPES[recipe.stem]['memory'])
                    # Default
                    else:
                        file.write(f'#PBS -l mem={memory}\n')
                if mail:
                    file.write('#PBS -m e \n')
                    file.write('#PBS -M romain.beucher@anu.edu.au \n')
                file.write('\n')
                file.write('module purge \n')
                file.write('module load pbs \n')
                file.write('\n')
                file.write('module use /g/data/xp65/public/modules\n')
                file.write(f'module load {env}\n')
                file.write('\n')
                file.write(f'run ../{str(recipe)}')
                if recipe.stem in ONE_TASK_RECIPES:
                    file.write(' --max_parallel_tasks=1')

            if submit:
                subprocess.check_call(['qsub', filename])


def generate_actions():
    """Generate GitHub action scripts."""
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("recipe_template.txt")

    for key, val in dir_recipes.items():
        for recipe in Path(val).rglob('*.ipynb'):
            filename = f'{recipe.stem}.yml'
            if recipe.stem in exclude:
                continue
            content = template.render(
                recipe=recipe.stem,
            )
            with open(f'../.github/workflows/{filename}', 'w', encoding='utf-8') as file:
                file.write(content)


def check_string_in_file(string, file):
    with open(file) as f:
        if string in f.read():
            return True
        else:
            return False


def generate_readme():
    """Generate Readme for GitHub."""
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("readme_template.txt")

    kwargs = {key:list() for key, val in dir_recipes.items()}

    for key, val in dir_recipes.items():
        for recipe in Path(val).rglob('*.ipynb'):
            if recipe.stem in exclude:
                continue
            kwargs[key].append(recipe.stem)

    content = template.render(**kwargs)

    with open('../README.md', 'w', encoding='utf-8') as file:
        file.write(content)


if __name__ == '__main__':
    generate_submit()
    generate_actions()
    generate_readme()
