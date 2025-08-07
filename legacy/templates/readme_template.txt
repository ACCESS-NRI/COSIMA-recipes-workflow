{# templates/readme_template.txt #}

# ACCESS-NRI MED COSIMA-recipes Workflow

ACCESS-NRI maintenance of COSIMA-recipes for the Australian Community.

## ACCESS-OM2 GMD Paper

| Name     |      status   |
|----------|:-------------|{% for recipe in access_om2 %} 
| {{ recipe }} | [![{{ recipe }}](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml/badge.svg)](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml) |{% endfor %}

## Contributed Examples

| Name     |      status   |
|----------|:-------------|{% for recipe in contributed %} 
| {{ recipe }} | [![{{ recipe }}](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml/badge.svg)](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml) |{% endfor %}

## Documented Examples

| Name     |      status   |
|----------|:-------------|{% for recipe in documented %} 
| {{ recipe }} | [![{{ recipe }}](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml/badge.svg)](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml) |{% endfor %}

## Tutorials

| Name     |      status   |
|----------|:-------------|{% for recipe in tutorials %} 
| {{ recipe }} | [![{{ recipe }}](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml/badge.svg)](https://github.com/ACCESS-NRI/COSIMA-recipes-workflow/actions/workflows/{{ recipe }}.yml) |{% endfor %}
