# Bellatrix

Bellatrix is a CPU core that implements the [RISC-V RV32I Instruction Set][1].
It is based on the [Minerva][2] CPU.

Bellatrix is free and open hardware licensed under the permissive two-clause BSD license.
See LICENSE file for full copyright and license information.

<!-- TOC -->

- [Bellatrix](#bellatrix)
    - [CPU core details](#cpu-core-details)
    - [Project Details](#project-details)
    - [Directory Layout](#directory-layout)
    - [Prerequisites](#prerequisites)
    - [Generate the core](#generate-the-core)
        - [Configuration file](#configuration-file)
        - [Top module pinout](#top-module-pinout)
    - [Building the simulator](#building-the-simulator)
    - [Running the compliance tests](#running-the-compliance-tests)
    - [Simulate execution of a single ELF file](#simulate-execution-of-a-single-elf-file)
            - [Parameters of the C++ model](#parameters-of-the-c-model)

<!-- /TOC -->

## CPU core details

- RISC-V RV32I[M] ISA.
- Single-issue, in-order, six-stage pipeline datapath.
- Separate instruction and data ports.
- Optional branch predictor.
- Optional instruction and data caches. The data cache is couple with a write buffer.
- Optional multiplier and divider, for the RV32M ISA.
- No MMU.
- No FPU. Software-base floating point support (toolchain).
- Support for Machine and User (optional) [privilege modes][3], version v1.11.
- Support for external interrupts, as described in the [privilege mode manual][3].
- Support for hardware triggers, as described in the [debug specification][11].
- [Wishbone B4][4] Bus Interface, in classic standard mode.

## Project Details

- Core described in python, using the [nMigen][5] toolbox.
- Simulation using [Verilator][6].

## Directory Layout

- `bellatrix`: Main package.
  - `config`: YAML configuration files for CPU variants.
  - `verilator`: Source files for the simulation.
  - `gateware`: CPU source files.
- `LICENSE`: Two-clause BSD license.
- `README.md`: This file.
- `cli.py`: Command line for code generation.

## Prerequisites

To generate the verilog file, you need to install:

- [Yosys][10] v0.9 or newer.
- [nMigen][4].
- [nMigen-soc][12].

Beware that [nMigen-soc][12] requieres a older version of [nMigen][4], so force-install it.

To build the simulator:
- [Verilator][6].
- libelf.

To run the RISC-V compliance tests:
- [RISC-V compiler toolchain][9].
- [RISC-V compliance tests][7].

## Generate the core

To generate a verilog file:

```
python3 cli.py generate --variant VARIANT [--config yaml] [--verbose] path/to/output/file.v
```

Options for VARIANT:

| Variant         | Description
| -------         | -----------
| `minimal`       | Optional features deactivated
| `lite`          | RV32M ISA enabled
| `standard`      | `Lite` configuration plus branch predictor enabled
| `full`          | `Standard` configuration plus caches enabled
| `minimal-debug` | `Minimal` configuration plus HW triggers enabled
| `custom`        | Custom YAML file using the `config` argument

### Configuration file

The configuration is done using a YAML file. The folder `bellatrix/config` has some configuration examples.

The following parameters are used to configure the core:

| Section     | Property           | Default value | Description
| ----------- | ------------------ | ------------- | ------------------------------------------
| `core`      | `reset_address`    | `0x80000000`  | Reset address
| `isa`       | `enable_rv32m`     | `False`       | Enable instructions for ISA RV32M
|             | `enable_extra_csr` | `False`       | Enable implementations of `misa`, `mhartid`, `mipid`, `marchid` and `mvendorid`
|             | `enable_user_mode` | `False`       | Enable User priviledge mode.
| `predictor` | `enable_predictor` | `False`       | Enable branch predictor implementation
|             | `size`             | `4096`        | Size of branch cache (power of 2)
| `icache`    | `enable`           | `False`       | Enable instruction cache
|             | `nlines`           | `512`         | Number of lines (power of 2)
|             | `nwords`           | `8`           | Number of words per line. Valid: 4, 8 and 16
|             | `nways`            | `1`           | Associativity. Valid: 1, 2
|             | `start_addr`       | `0x80000000`  | Start address of cacheable region
|             | `end_addr`         | `0xffffffff`  | Final address of cacheable region
| `dcache`    | `enable`           | `False`       | Enable instruction cache
|             | `nlines`           | `512`         | Number of lines (power of 2)
|             | `nwords`           | `8`           | Number of words per line. Valid: 4, 8 and 16
|             | `nways`            | `1`           | Associativity. Valid: 1, 2
|             | `start_addr`       | `0x80000000`  | Start address of cacheable region
|             | `end_addr`         | `0xffffffff`  | Final address of cacheable region
| `trigger`   | `enable`           | `False`       | Enable implementation of hardware (trigger) breakpoints
|             | `ntriggers`        | `4`           | Number of hardware (trigger) breakpoints

### Top module pinout

The pinout for the top module, `bellatrix_core`:

| Port name          | Size | Description
| ------------------ | ---- | -----------
| clk                | 1    | System clock
| rst                | 1    | System reset
| iport__addr        | 32   | Wishbone instruction Address port (output)
| iport__dat_w       | 32   | Wishbone instruction Write Data port (output)
| iport__sel         | 4    | Wishbone instruction Select port (output)
| iport__we          | 1    | Wishbone instruction Write Enable port (output)
| iport__cyc         | 1    | Wishbone instruction Cycle port (output)
| iport__stb         | 1    | Wishbone instruction Strobe port (output)
| iport__cti         | 3    | Wishbone instruction Cycle Type Identifier port (output) (if icache_enable = True)
| iport__bte         | 2    | Wishbone instruction Burst Type Extension port (output) (if icache_enable = True)
| iport__dat_r       | 32   | Wishbone instruction Data Read port (input)
| iport__ack         | 1    | Wishbone instruction Acknowledge port (input)
| iport__err         | 1    | Wishbone instruction Error port (input)
| dport__addr        | 32   | Wishbone data Address port (output)
| dport__dat_w       | 32   | Wishbone data Write Data port (output)
| dport__sel         | 4    | Wishbone data Select port (output)
| dport__we          | 1    | Wishbone data Write Enable port (output)
| dport__cyc         | 1    | Wishbone data Cycle port (output)
| dport__stb         | 1    | Wishbone data Strobe port (output)
| dport__cti         | 3    | Wishbone data Cycle Type Identifier port (output) (if dcache_enable = True)
| dport__bte         | 2    | Wishbone data Burst Type Extension port (output) (if dcache_enable = True)
| dport__dat_r       | 32   | Wishbone data Data Read port (input)
| dport__ack         | 1    | Wishbone data Acknowledge port (input)
| dport__err         | 1    | Wishbone data Error port (input)
| external_interrupt | 1    | External interrupt input signal
| timer_interrupt    | 1    | Timer interrupt input signal
| software_interrupt | 1    | Software interrupt input signal

## Building the simulator

To build the simulator:

```
python3 cli.py buildtb --variant VARIANT [--config CONFIG]
```

This creates a executable in `<current folder>/build/<variant>/core.exe`, which can be used to execute the RISC-V compliance tests, or execute bare-metal programs.

## Running the compliance tests

To run the [riscv-compliance][7], it is necessary to first download the [repository][7]:

```
git clone https://github.com/AngelTerrones/riscv-compliance path/to/rvcompliance
cd path/to/rvcompliance
git checkout nht-cores
```

Then, define the the variable `RVGCC_PATH` to the `bin` folder of the RISC-V GCC toolchain:

```
export RVGCC_PATH=/path/to/bin/folder/of/riscv-gcc
```

The easy way to get the toolchain is to download a prebuilt version from [SiFive][8].
The version used to compile the tests is [riscv64-unknown-elf-gcc-8.3.0-2019.08.0][9]

Finally, execute the desired test:

```
python3 cli.py compliance --rvc path/to/rvcompliance --variant VARIANT [--config CONFIG] --isa ISA1 [ISA1, ISA2, ...]
```

Note:
- The `rv32im` compliance tests requieres enabling the RV32M ISA.
- The `breakpoint` test in the `rv32mi` compliance set requieres enabling the `trigger` module.

## Simulate execution of a single ELF file

To execute a single `.elf` file, first build the desired simulator, then:

```
./build/<variant>/core.exe --file [ELF file] --timeout [max time] --signature [signature file] --trace
```

#### Parameters of the C++ model

- `file`: RISC-V ELF file to execute.
- `timeout`: (Optional) Maximum simulation time before aborting.
- `signature`: (Optional) Write memory dump to a file. For verification purposes.
- `trace`: (Optional) Enable VCD dumps. Writes the output file to `build/trace_core.vcd`.

[1]: https://riscv.org/specifications/
[2]: https://github.com/lambdaconcept/minerva
[3]: https://riscv.org/specifications/privileged-isa/
[4]: https://www.ohwr.org/attachments/179/wbspec_b4.pdf
[5]: https://github.com/nmigen/nmigen/
[6]: https://www.veripool.org/wiki/verilator
[7]: http://github.com/angelterrones/riscv-compliance
[8]: https://www.sifive.com/boards
[9]: https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2019.08.0-x86_64-linux-ubuntu14.tar.gz
[10]: https://github.com/YosysHQ/yosys
[11]: https://riscv.org/specifications/debug-specification/
[12]: https://github.com/nmigen/nmigen-soc
