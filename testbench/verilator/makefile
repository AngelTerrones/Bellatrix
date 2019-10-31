# ------------------------------------------------------------------------------
# Copyright (c) 2019 Angel Terrones <angelterrones@gmail.com>
# ------------------------------------------------------------------------------
include pprint.mk

# verilate
#--------------------------------------------------
EXE			:= core
ROOT		?= $(shell cd ../../; pwd)
RTLDIR		?= $(ROOT)/build
TBDIR		:= verilog
VSOURCES	:= $(shell find $(RTLDIR) $(TBDIR) -name "*.v")
VTOP		:= $(TBDIR)/top.v
#--------------------------------------------------
VOUT		?= $(ROOT)/build
VOBJ		:= $(VOUT)/obj_dir_$(EXE)
SUBMAKE		:= $(MAKE) --no-print-directory --directory=$(VOBJ) -f
NO_WARN     := -Wno-fatal -Wno-DECLFILENAME -Wno-CASEINCOMPLETE -Wno-CASEOVERLAP -Wno-WIDTH -Wno-UNUSED
VERILATE	:= verilator -O3 --trace -Wall $(NO_WARN) --x-assign 1 -cc -y $(RTLDIR) -y $(TBDIR) \
						 -CFLAGS "-std=c++11 -O3 -DDPI_DLLISPEC= -DDPI_DLLESPEC=" -Mdir $(VOBJ)

#--------------------------------------------------
# C++ build
CXX			:= g++
CFLAGS		:= -std=c++17 -Wall -O3 -DDPI_DLLISPEC= -DDPI_DLLESPEC= -MD -MP #-g #-DDEBUG #-Wno-sign-compare
CFLAGS_NEW	:= -faligned-new -Wno-attributes
CFLAGS_V	:= -Wno-sign-compare
VROOT		:= $(shell bash -c 'verilator -V|grep VERILATOR_ROOT | head -1 | sed -e " s/^.*=\s*//"')
VINCD		:= $(VROOT)/include
VINC		:= -I$(VINCD) -I$(VINCD)/vltstd -I$(VOBJ)

#--------------------------------------------------
INCS := $(VINC) -Itests/verilator

#--------------------------------------------------
VOBJS		:= $(VOBJ)/verilated.o $(VOBJ)/verilated_vcd_c.o $(VOBJ)/verilated_dpi.o
SOURCES		:= aelf.cpp coretb.cpp main.cpp ram.cpp
OBJS		:= $(addprefix $(VOBJ)/, $(subst .cpp,.o,$(SOURCES)))
DEPFILES	:= $(addprefix $(VOBJ)/, $(subst .cpp,.d,$(SOURCES)))

# ------------------------------------------------------------------------------
# targets
# ------------------------------------------------------------------------------
all: build-core
build-core: $(VSOURCES) $(VOBJ)/Vtop__ALL.a $(VOUT)/$(EXE).exe

run: build-core
	$(VOUT)/$(EXE).exe $(ARGS)

clean:
	rm -rf $(VOBJ)

.SECONDARY: $(OBJS)

# Verilator
$(VOBJ)/Vtop__ALL.a: $(VSOURCES)
	@mkdir -p $(VOUT)
	@printf "%b" "$(COM_COLOR)$(VER_STRING)$(OBJ_COLOR) $(VTOP) $(NO_COLOR)\n"
	+@$(VERILATE) $(VTOP)
	@printf "%b" "$(COM_COLOR)$(COM_STRING)$(OBJ_COLOR) $(@F)$(NO_COLOR)\n"
	+@$(SUBMAKE) Vtop.mk

# C++
$(VOBJ)/%.o: cpp/%.cpp
	@printf "%b" "$(COM_COLOR)$(COM_STRING)$(OBJ_COLOR) $(@F) $(NO_COLOR)\n"
	@$(CXX) $(CFLAGS) -DEXE="\"$(EXE)\"" $(INCS) -c $< -o $@

$(VOBJS): $(VOBJ)/%.o: $(VINCD)/%.cpp
	@printf "%b" "$(COM_COLOR)$(COM_STRING)$(OBJ_COLOR) $(@F) $(NO_COLOR)\n"
	@$(CXX) $(CFLAGS) $(INCS) $(CFLAGS_V) -c $< -o $@

$(VOUT)/$(EXE).exe: $(VOBJS) $(OBJS) $(VOBJ)/Vtop__ALL.a
	@printf "%b" "$(COM_COLOR)$(COM_STRING)$(OBJ_COLOR) $(@F)$(NO_COLOR)\n"
	@$(CXX) $(INCS) $^ -lelf -o $@
	@printf "%b" "$(MSJ_COLOR)Compilation $(OK_COLOR)$(OK_STRING)$(NO_COLOR)\n"

-include $(DEPFILES)
