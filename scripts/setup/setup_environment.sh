#!/usr/bin/env bash

VENV=$ROOT/.venv

if [ -d "$VENV" ]; then
    echo "Deleting old virtualenv"
    rm -rf $VENV
fi

echo "Creating python virtual environment"
python3 -m venv $VENV
echo "Installing nMigen"
source $VENV/bin/activate
pip3 install flake8 rope wheel
pip3 install git+https://github.com/m-labs/nmigen.git
deactivate
echo "Virtualenv setup: DONE"
