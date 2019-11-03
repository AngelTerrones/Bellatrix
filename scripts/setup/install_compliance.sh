#!/usr/bin/env bash

RVCOMPLIANCE=$ROOT/tests/riscv-compliance

if [ ! -d "$RVCOMPLIANCE" ]; then
    echo "Downloading riscv-compliance"
    git clone https://github.com/AngelTerrones/riscv-compliance $RVCOMPLIANCE
    cd $RVCOMPLIANCE
    git checkout nht-cores
    echo "Done!"
else
    cd $RVCOMPLIANCE
    git checkout nht-cores
    git pull
    echo "Done!"
fi
