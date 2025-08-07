#!/bin/bash

if [ ! -d "cosima-recipes" ]
then
  git clone git@github.com:ACCESS-NRI/cosima-recipes.git
fi
rm ../.github/workflows/*.yml
python generate.py

