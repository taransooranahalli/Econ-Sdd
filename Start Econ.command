#!/bin/zsh
set -eu
project_dir="${0:A:h}"
cd "$project_dir"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  print 'Create the project virtual environment using the instructions in README.md.'
  read '?Press Enter to close.'
  exit 1
fi
print 'Econ runs locally at http://127.0.0.1:8004/'
print 'Keep this Terminal open while using the app. Press Ctrl-C to stop it.'
exec "$project_dir/.venv/bin/python" -m econ_sdd
