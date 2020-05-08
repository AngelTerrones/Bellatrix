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
CLI_FILE=$(ROOT)/cli.py
VERBOSE=--verbose

VARIANTS=minimal lite standard full minimal_debug
GEN_FOLDER=$(BFOLDER)/$(VARIANT)

OBJ_FOLDER_DEL=$(shell find $(BFOLDER) -name "*obj_*")

# export variables
export ROOT
export RISCV_PREFIX ?= $(RVGCC_PATH)/riscv64-unknown-elf-
export TARGET_FOLDER = $(VCOREDIR)
export RTLDIR = $(GEN_FOLDER)
export VOUT = $(GEN_FOLDER)
export VARIANT

# ------------------------------------------------------------------------------
# targetsEXE
# ------------------------------------------------------------------------------
help:
	@echo -e "--------------------------------------------------------------------------------"
	@echo -e $(BYellow)"Please, choose one target:"$(Color_Off)
	@echo -e $(BPurple)"Generate:"$(Color_Off)
	@echo -e "- generate-core:                    Generate verilog from the design."
	@echo -e "- generate-core-all:                Generate all the verilog files, one for each available VARIANT."
	@echo -e $(BBlue)"Build:"$(Color_Off)
	@echo -e "- build-core:                       Build the verilator testbench."
	@echo -e "- build-core-all:                   Build ALL verilator testbenches."
	@echo -e $(BGreen)"Execute tests:"$(Color_Off)
	@echo -e "- core-sim-compliance-basic:        Execute the rv32i, rv32ui and rv32mi tests."
	@echo -e "- core-sim-compliance-extra:        Execute the rv32i, rv32ui, rv32mi, rv32Zicsr and rv32Zifencei tests."
	@echo -e "- core-sim-compliance:              Execute the rv32i, rv32ui, rv32mi, rv32Zicsr, rv32Zifencei and rv32im tests."
	@echo -e "- core-sim-compliance-rv32i:        Execute the RV32I compliance tests."
	@echo -e "- core-sim-compliance-rv32im:       Execute the RV32IM compliance tests."
	@echo -e "- core-sim-compliance-rv32mi:       Execute machine mode compliance tests."
	@echo -e "- core-sim-compliance-rv32ui:       Execute the RV32I compliance tests (redundant)."
	@echo -e "- core-sim-compliance-rv32Zicsr:    Execute the RV32Zicsr compliance tests."
	@echo -e "- core-sim-compliance-rv32Zifencei: Execute the RV32Zifencei compliance test."
	@echo -e "--------------------------------------------------------------------------------"

# ------------------------------------------------------------------------------
# compliance tests
# ------------------------------------------------------------------------------
core-sim-compliance-basic: core-sim-compliance-rv32i core-sim-compliance-rv32ui core-sim-compliance-rv32mi

core-sim-compliance-extra: core-sim-compliance-basic core-sim-compliance-rv32Zicsr core-sim-compliance-rv32Zifencei

core-sim-compliance: core-sim-compliance-extra core-sim-compliance-rv32im

core-sim-compliance-rv32i: build-core
	@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32i RISCV_ISA=rv32i

core-sim-compliance-rv32im: build-core
	-@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32im RISCV_ISA=rv32im

core-sim-compliance-rv32mi: build-core
	-@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32i RISCV_ISA=rv32mi

core-sim-compliance-rv32ui: build-core
	@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32i RISCV_ISA=rv32ui

core-sim-compliance-rv32Zicsr: build-core
	@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32i RISCV_ISA=rv32Zicsr

core-sim-compliance-rv32Zifencei: build-core
	@$(SUBMAKE) -C $(RVCOMPLIANCE) variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32i RISCV_ISA=rv32Zifencei

build-extra-tests:
	$(SUBMAKE) -C tests/extra-tests

# ------------------------------------------------------------------------------
# Generate core, verilate, and build
# ------------------------------------------------------------------------------
generate-core: $(GEN_FOLDER)/bellatrix_core.v

generate-core-all:
	+@$(foreach variant, $(VARIANTS), make generate-core VARIANT=$(variant) VERBOSE= --no-print-directory ;)

build-core: generate-core
	+@$(SUBMAKE) -C $(VCOREDIR)

build-core-all:
	+@$(foreach variant, $(VARIANTS), make build-core VARIANT=$(variant) VERBOSE=;)
# ------------------------------------------------------------------------------
# HIDDEN
# ------------------------------------------------------------------------------
$(GEN_FOLDER)/bellatrix_core.v: $(CORE_FILES) $(CLI_FILE) configurations/bellatrix_$(VARIANT).yml
	@mkdir -p $(GEN_FOLDER)
	@echo -e "Generate core:" $(BGreen)$(VARIANT)$(Color_Off)
	@python $(CLI_FILE) $(VERBOSE) --variant $(VARIANT) generate $(GEN_FOLDER)/bellatrix_core.v
#   @echo -e "Generate core:" $(BGreen)Done!$(Color_Off)

# ------------------------------------------------------------------------------
# clean
# ------------------------------------------------------------------------------
clean:
	rm -rf $(OBJ_FOLDER_DEL)

distclean:
	@$(SUBMAKE) -C $(RVCOMPLIANCE) clean
	rm -rf $(BFOLDER)
