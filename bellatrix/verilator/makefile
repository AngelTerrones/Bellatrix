# ------------------------------------------------------------------------------
# Copyright (c) 2019 Angel Terrones <angelterrones@gmail.com>
# ------------------------------------------------------------------------------
include $TVERILATOR/pprint.mk

# verilate
#--------------------------------------------------
EXE			:= core
RTLDIR		:= .
TVERILATOR	:= $TVERILATOR
TBDIR		:= $$(TVERILATOR)/verilog
VSOURCES	:= $$(shell find $$(RTLDIR) $$(TBDIR) -name "*.v")
VTOP		:= $$(RTLDIR)/top.v
#--------------------------------------------------
VOBJ		:= obj_dir_$$(EXE)
SUBMAKE		:= $$(MAKE) --no-print-directory --directory=$$(VOBJ) -f
NO_WARN     := -Wno-fatal -Wno-DECLFILENAME -Wno-CASEINCOMPLETE -Wno-CASEOVERLAP -Wno-WIDTH -Wno-UNUSED
VERILATE	:= verilator -O3 --trace -Wall $$(NO_WARN) --x-assign 1 -cc -y $$(RTLDIR) -y $$(TBDIR) \
						 -CFLAGS "-std=c++11 -O3 -DDPI_DLLISPEC= -DDPI_DLLESPEC=" -Mdir $$(VOBJ) \
						 --timescale-override "1ns/1ns"

#--------------------------------------------------
# C++ build
CXX			:= g++
CFLAGS		:= -std=c++17 -Wall -O3 -DDPI_DLLISPEC= -DDPI_DLLESPEC= -MD -MP #-g #-DDEBUG #-Wno-sign-compare
CFLAGS_NEW	:= -faligned-new -Wno-attributes
CFLAGS_V	:= -Wno-sign-compare
VROOT		:= $$(shell bash -c 'verilator -V|grep VERILATOR_ROOT | head -1 | sed -e " s/^.*=\s*//"')
VINCD		:= $$(VROOT)/include
VINC		:= -I$$(VINCD) -I$$(VINCD)/vltstd -I$$(VOBJ)
VTBINC		:= $$(TVERILATOR)/cpp
#--------------------------------------------------
INCS := $$(VINC)
#--------------------------------------------------
VOBJS		:= $$(VOBJ)/verilated.o $$(VOBJ)/verilated_vcd_c.o $$(VOBJ)/verilated_dpi.o
SOURCES		:= aelf.cpp coretb.cpp main.cpp ram.cpp
OBJS		:= $$(addprefix $$(VOBJ)/, $$(subst .cpp,.o,$$(SOURCES)))
DEPFILES	:= $$(addprefix $$(VOBJ)/, $$(subst .cpp,.d,$$(SOURCES)))

# ------------------------------------------------------------------------------
# targets
# ------------------------------------------------------------------------------
all: build-core
build-core: $$(VSOURCES) $$(VOBJ)/Vtop__ALL.a $$(EXE).exe

run: build-core
	./$$(EXE).exe $$(ARGS)

clean:
	rm -rf $$(VOBJ)

.SECONDARY: $$(OBJS)

# Verilate
$$(VOBJ)/Vtop.mk: $$(VSOURCES)
	@printf "%b" "$$(COM_COLOR)$$(VER_STRING)$$(OBJ_COLOR) $$(VTOP) $$(NO_COLOR)\n"
	+@$$(VERILATE) $$(VTOP)

$$(VOBJ)/Vtop__ALL.a: $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F)$$(NO_COLOR)\n"
	+@$$(SUBMAKE) Vtop.mk

# Verilator
$$(VOBJ)/verilated.o: $$(VINCD)/verilated.cpp $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F) $$(NO_COLOR)\n"
	$$(CXX) $$(CFLAGS) $$(INCS) $$(CFLAGS_V) -c $$< -o $$@

$$(VOBJ)/verilated_vcd_c.o: $$(VINCD)/verilated_vcd_c.cpp $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F) $$(NO_COLOR)\n"
	$$(CXX) $$(CFLAGS) $$(INCS) $$(CFLAGS_V) -c $$< -o $$@

$$(VOBJ)/verilated_dpi.o: $$(VINCD)/verilated_dpi.cpp $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F) $$(NO_COLOR)\n"
	$$(CXX) $$(CFLAGS) $$(INCS) $$(CFLAGS_V) -c $$< -o $$@

# Bellatrix
$$(VOBJ)/aelf.o: $$(VTBINC)/aelf.cpp $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F) $$(NO_COLOR)\n"
	$$(CXX) $$(CFLAGS) -DEXE="\"$$(EXE)\"" -DBCONFIG="\"$$(BCONFIG)\"" $$(INCS) -c $$< -o $$@

$$(VOBJ)/coretb.o: $$(VTBINC)/coretb.cpp $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F) $$(NO_COLOR)\n"
	$$(CXX) $$(CFLAGS) -DEXE="\"$$(EXE)\"" -DBCONFIG="\"$$(BCONFIG)\"" $$(INCS) -c $$< -o $$@

$$(VOBJ)/main.o: $$(VTBINC)/main.cpp $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F) $$(NO_COLOR)\n"
	$$(CXX) $$(CFLAGS) -DEXE="\"$$(EXE)\"" -DBCONFIG="\"$$(BCONFIG)\"" $$(INCS) -c $$< -o $$@

$$(VOBJ)/ram.o: $$(VTBINC)/ram.cpp $$(VOBJ)/Vtop.mk
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F) $$(NO_COLOR)\n"
	$$(CXX) $$(CFLAGS) -DEXE="\"$$(EXE)\"" -DBCONFIG="\"$$(BCONFIG)\"" $$(INCS) -c $$< -o $$@

# Exe
$$(EXE).exe: $$(VOBJS) $$(OBJS) $$(VOBJ)/Vtop__ALL.a
	@printf "%b" "$$(COM_COLOR)$$(COM_STRING)$$(OBJ_COLOR) $$(@F)$$(NO_COLOR)\n"
	$$(CXX) $$(INCS) $$^ -lelf -o $$@
	@printf "%b" "$$(MSJ_COLOR)Compilation $$(OK_COLOR)$$(OK_STRING)$$(NO_COLOR)\n"

-include $$(DEPFILES)
