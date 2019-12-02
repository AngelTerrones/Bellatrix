#!/usr/bin/env bash

Color_Off='\033[0m'
BGreen='\033[1;32m'
BYellow='\033[1;33m'

RVCOMPLIANCE=$ROOT/tests/riscv-compliance

if [ ! -d "$RVCOMPLIANCE" ]; then
    echo -e ${BYellow}"Downloading riscv-compliance"${Color_Off}
    git clone https://github.com/AngelTerrones/riscv-compliance $RVCOMPLIANCE
    cd $RVCOMPLIANCE
    git checkout nht-cores
    echo -e ${BGreen}"Done!"${Color_Off}
else
    cd $RVCOMPLIANCE
    echo -e ${BYellow}"Moving to branch 'nht-cores'"${Color_Off}
    git checkout nht-cores
    echo -e ${BYellow}"Updating repository"${Color_Off}
    git pull
    echo -e ${BGreen}"Done!"${Color_Off}
fi
