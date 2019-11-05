# ------------------------------------------------------------------------------
# Copyright (c) 2019 Angel Terrones <angelterrones@gmail.com>
# ------------------------------------------------------------------------------
SHELL=bash

Color_Off='\033[0m'
# Bold colors
BBlack='\033[1;30m'
BRed='\033[1;31m'
BGreen='\033[1;32m'
BYellow='\033[1;33m'
BBlue='\033[1;34m'
BPurple='\033[1;35m'
BCyan='\033[1;36m'
BWhite='\033[1;37m'

# ------------------------------------------------------------------------------
SUBMAKE	 = $(MAKE) --no-print-directory
ROOT	 = $(shell pwd)
BFOLDER	 = $(ROOT)/build
VCOREDIR = $(ROOT)/testbench/verilator

CORE_FILES=$(shell find bellatrix -name "*.py")
BUILD_FILE=$(ROOT)/scripts/build.py

CFG_FILES=$(shell find configurations -name "*.ini")
CFG_BASENAME=$(basename $(notdir $(CONFIG)))
GEN_FOLDER=$(BFOLDER)/$(CFG_BASENAME)

OBJ_FOLDER_DEL=$(shell find $(BFOLDER) -name "*obj_*")

# Compliance tests + xint test
RVCOMPLIANCE = $(ROOT)/tests/riscv-compliance
RVXTRASF     = $(ROOT)/tests/extra-tests

# export variables
export ROOT
export RISCV_PREFIX ?= $(RVGCC_PATH)/riscv64-unknown-elf-
export TARGET_FOLDER = $(VCOREDIR)
export RTLDIR = $(GEN_FOLDER)
export VOUT = $(GEN_FOLDER)

# ------------------------------------------------------------------------------
# targets
# ------------------------------------------------------------------------------
help:
	@echo -e "--------------------------------------------------------------------------------"
	@echo -e "Please, choose one target:"
	@echo -e "- install-compliance:         Clone the riscv-compliance test."
	@echo -e "- setup_environment:          Create a python3 virtualenv, and installs nMigen."
	@echo -e "- generate-core:              Generate the verilog output file."
	@echo -e "- generate-core-all:          Generate ALL the verilog output file."
	@echo -e "- build-core:                 Build the verilator testbench."
	@echo -e "- build-core-all:             Build ALL verilator testbenches."
	@echo -e "- core-sim-compliance:        Execute the compliance tests."
	@echo -e "- core-sim-compliance-rv32i:  Execute the RV32I compliance tests."
	@echo -e "- core-sim-compliance-rv32im: Execute the RV32IM compliance tests."
	@echo -e "- core-sim-compliance-rv32mi: Execute machine mode compliance tests."
	@echo -e "- core-sim-compliance-rv32ui: Execute the RV32I compliance tests (redundant)."
	@echo -e "--------------------------------------------------------------------------------"

# ------------------------------------------------------------------------------
# Install compliance repo (custom one)
# ------------------------------------------------------------------------------
install-compliance:
	@./scripts/setup/install_compliance.sh
# ------------------------------------------------------------------------------
# compliance tests: TODO create custom targer Bellatrix in repo
# ------------------------------------------------------------------------------
core-sim-compliance: core-sim-compliance-rv32i core-sim-compliance-rv32ui core-sim-compliance-rv32mi core-sim-compliance-rv32im

core-sim-compliance-rv32i: build-core
	@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32i RISCV_ISA=rv32i

core-sim-compliance-rv32im: build-core
	-@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32im RISCV_ISA=rv32im

core-sim-compliance-rv32mi: build-core
	-@$(SUBuildthe verilator testbenchBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32mi RISCV_ISA=rv32mi

core-sim-compliance-rv32ui: build-core
	@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32ui RISCV_ISA=rv32ui

build-extra-tests:
	$(SUBMAKE) -C tests/extra-tests
# ------------------------------------------------------------------------------
# Create the development environment.
# ------------------------------------------------------------------------------
setup-environment:
	@./scripts/setup/setup_environment.sh
# ------------------------------------------------------------------------------
# Generate core, verilate, and build
# ------------------------------------------------------------------------------
generate-core: $(GEN_FOLDER)/bellatrix_core.v

generate-core-all:
	+@$(foreach cfg, $(CFG_FILES), make generate-core CONFIG=$(cfg);)

build-core: generate-core
	@mkdir -p $(BFOLDER)
	+@$(SUBMAKE) -C $(VCOREDIR)

build-core-all:
	+@$(foreach cfg, $(CFG_FILES), make build-core CONFIG=$(cfg);)
# ------------------------------------------------------------------------------
# HIDDEN
# ------------------------------------------------------------------------------
$(GEN_FOLDER)/bellatrix_core.v: $(CORE_FILES) $(BUILD_FILE) $(CONFIG)
	@mkdir -p $(GEN_FOLDER)
	@echo -e "Generate core:" $(BGreen)$(shell basename $(CONFIG))$(Color_Off)
	@PYTHONPATH=$(ROOT) python scripts/build.py --config-file $(CONFIG) generate $(GEN_FOLDER)/bellatrix_core.v
	@sed -i '/verilog_initial_trigger/d' $(GEN_FOLDER)/bellatrix_core.v

# ------------------------------------------------------------------------------
# clean
# ------------------------------------------------------------------------------
clean:
	rm -rf $(OBJ_FOLDER_DEL)

distclean: clean
	@$(SUBMAKE) -C $(RVCOMPLIANCE) clean
	@$(SUBMAKE) -C tests/extra-tests clean
	rm -rf $(BFOLDER)
