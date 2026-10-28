#!/bin/zsh
set -eu
project_dir="${0:A:h}"
cd "$project_dir"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  print 'Create the project virtual environment using the instructions in README.md.'
  read '?Press Enter to close.'
  exit 1
fi
exec "$project_dir/.venv/bin/python" -m econ_sdd
