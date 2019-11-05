read_verilog scripts/vivado/top.v
read_verilog build/bellatrix_rv32m_bp_ic_dc/bellatrix_core.v
read_xdc scripts/vivado/synth_speed.xdc

synth_design -part xc7a100tftg256-2 -top top
opt_design

report_utilization
report_timing
