#!/usr/bin/env bash

Color_Off='\033[0m'
BGreen='\033[1;32m'
BYellow='\033[1;33m'
BRed='\033[1;31m'

VENV=$ROOT/.venv

if [ -d "$VENV" ]; then
    echo -e ${BRed}"Deleting old virtualenv"${Color_Off}
    rm -rf $VENV
fi

echo -e ${BYellow}"Creating python virtual environment"${Color_Off}
python3 -m venv $VENV
source $VENV/bin/activate
echo -e ${BYellow}"Installing required packages for development"${Color_Off}
pip3 install flake8 rope wheel mypy
echo -e ${BYellow}"Installing nMigen"${Color_Off}
pip3 install git+https://github.com/m-labs/nmigen.git
deactivate
echo -e ${BGreen}"Virtualenv setup: DONE"${Color_Off}
