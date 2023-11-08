#!/bin/bash

if [ ! -d "cosima-recipes" ]
then
  git clone git@github.com:ACCESS-NRI/cosima-recipes.git
fi
rm ../.github/workflows/recipe*.yml
python generate.py

