![logo](documentation/img/logo.png)

Bellatrix is a CPU core that implements the [RISC-V RV32I Instruction Set][1].

Bellatrix is free and open hardware licensed under the permissive two-clause BSD license.
See LICENSE file for full copyright and license information.

<!-- TOC -->

- [CPU core details](#cpu-core-details)
- [Project Details](#project-details)
- [Directory Layout](#directory-layout)
- [RISC-V toolchain](#risc-v-toolchain)
- [Configuration File](#configuration-file)
- [Core generation.](#core-generation)
    - [Dependencies](#dependencies)
    - [Setup development environment](#setup-development-environment)
    - [Generate core](#generate-core)
    - [Top module pinout](#top-module-pinout)
- [Simulation](#simulation)
    - [Dependencies for simulation](#dependencies-for-simulation)
    - [Download the compliance tests](#download-the-compliance-tests)
    - [Define `RVGCC_PATH`](#define-rvgcc_path)
    - [Generate the C++ model and compile it](#generate-the-c-model-and-compile-it)
    - [Run the compliance tests](#run-the-compliance-tests)
    - [Simulate execution of a single ELF file](#simulate-execution-of-a-single-elf-file)
        - [Parameters of the C++ model](#parameters-of-the-c-model)
- [License](#license)

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
- Machine [privilege mode][2]. Current version: v1.11.
- Support for external interrupts, as described in the [privilege mode manual][2].
- [Wishbone B4][3] Bus Interface, in classic mode.

## Project Details

- Core described in python, using the [nMigen][4] toolbox.
- Simulation done in C++ using [Verilator][5].
- [Toolchain][6] using gcc.
- [Validation suit][7] written in assembly.

## Directory Layout

- `bellatrix`: CPU source files.
- `configurations`: Configurations examples.
- `scripts`: Scripts for installation of compliance tests, and setup development environment.
- `testbench`: Verilator testbench, written in C++.
- `tests`: Assembly test environment for the CPU.
  - `extra_tests`: Aditional test for the software, timer and external interrupt interface.
- `LICENSE`: Two-clause BSD license.
- `README.md`: This file.

## RISC-V toolchain

The easy way to get the toolchain is to download a prebuilt version from [SiFive][8].

The version used to compile the tests is [riscv64-unknown-elf-gcc-8.3.0-2019.08.0][9]

## Configuration File

The following parameters are used to configure the core:

| Section     | Property           | Default value | Description
| ----------- | ------------------ | ------------- | ------------------------------------------
| `reset`     | `reset_address`    | `0x80000000`  | Reset address
| `isa`       | `enable_rv32m`     | `True`        | Enable instructions for ISA RV32M
|             | `enable_extra_csr` | `True`        | Enable implementations of `misa`, `mhartid`, `mipid`, `marchid` and `mvendorid`
| `predictor` | `enable_predictor` | `True`        | Enable branch predictor implementation
|             | `size`             | `4096`        | Size of branch cache (power of 2)
| `icache`    | `enable`           | `True`        | Enable instruction cache
|             | `nlines`           | `512`         | Number of lines (power of 2)
|             | `nwords`           | `8`           | Number of words per line. Valid: 4, 8 and 16
|             | `nways`            | `1`           | Associativity. Valid
|             | `start_addr`       | `0x80000000`  | Start address of cacheable region
|             | `end_addr`         | `0xffffffff`  | Final address of cacheable region
| `dcache`    | `enable`           | `True`        | Enable instruction cache
|             | `nlines`           | `512`         | Number of lines (power of 2)
|             | `nwords`           | `8`           | Number of words per line. Valid: 4, 8 and 16
|             | `nways`            | `1`           | Associativity. Valid
|             | `start_addr`       | `0x80000000`  | Start address of cacheable region
|             | `end_addr`         | `0xffffffff`  | Final address of cacheable region

## Core generation.
### Dependencies
[nMigen][4] requieres [Yosys][10] 0.9 or newer. So install it first.

### Setup development environment

To create a virtualenv and install [nMigen][4], execute the following command:
> make setup-environment

or just follow the install instructions in the [nMigen][4] page.

### Generate core

Activate the virtualenv:
> source .venv/bin/activate

Generate the core using a configuration file:
> make generate-core CONFIG=/path/to/configuration.ini

The verilog file will be in `build/name_of_configuration_file/bellatrix_core.v`

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
| iport__cti         | 3    | Wishbone instruction Cycle Type Identifier port (output)
| iport__bte         | 2    | Wishbone instruction Burst Type Extension port (output)
| iport__dat_r       | 32   | Wishbone instruction Data Read port (input)
| iport__ack         | 1    | Wishbone instruction Acknowledge port (input)
| iport__err         | 1    | Wishbone instruction Error port (input)
| dport__addr        | 32   | Wishbone data Address port (output)
| dport__dat_w       | 32   | Wishbone data Write Data port (output)
| dport__sel         | 4    | Wishbone data Select port (output)
| dport__we          | 1    | Wishbone data Write Enable port (output)
| dport__cyc         | 1    | Wishbone data Cycle port (output)
| dport__stb         | 1    | Wishbone data Strobe port (output)
| dport__cti         | 3    | Wishbone data Cycle Type Identifier port (output)
| dport__bte         | 2    | Wishbone data Burst Type Extension port (output)
| dport__dat_r       | 32   | Wishbone data Data Read port (input)
| dport__ack         | 1    | Wishbone data Acknowledge port (input)
| dport__err         | 1    | Wishbone data Error port (input)
| external_interrupt | 1    | External interrupt input signal
| timer_interrupt    | 1    | Timer interrupt input signal
| software_interrupt | 1    | Software interrupt input signal

## Simulation
### Dependencies for simulation

- [Verilator][5]. Minimum version: 4.0.
- libelf.
- The official RISC-V [toolchain][8].

### Download the compliance tests

To download the [riscv-compliance][7] repository:
> make install-compliance

This downloads a fork of [riscv-compliance][7] with added support for this core.

### Define `RVGCC_PATH`
Before running the compliance test suit, benchmarks and extra-tests, define the variable `RVGCC_PATH` to the `bin` folder of the toolchain:
> export RVGCC_PATH=/path/to/bin/folder/

### Generate the C++ model and compile it
To compile the verilator testbench, execute the following command in the root folder of
the project:
> $ make build-core CONFIG=/path/to/configuration.ini

### Run the compliance tests
To perform the simulation, execute the following command in the root folder of
the project:
> $ make core-sim-compliance CONFIG=/path/to/configuration.ini

All tests should pass, with exception of the `breakpoint` test: no debug module has been implemented.

### Simulate execution of a single ELF file

To execute a single `.elf` file:

> $ ./build/name_of_configuration_file/core.exe --file [ELF file] --timeout [max time] --signature [signature file] --trace

#### Parameters of the C++ model

- `file`: RISC-V ELF file to execute.
- `timeout (optional)`: Maximum simulation time before aborting.
- `signature (optional)`: Write memory dump to a file. For verification purposes.
- `trace (optional)`: Enable VCD dumps. Writes the output file to `build/trace_core.vcd`.

## License
Copyright (c) 2019 Angel Terrones (<angelterrones@gmail.com>).

Rreleased under the permissive two-clause BSD license.

[1]: https://riscv.org/specifications/
[2]: https://riscv.org/specifications/privileged-isa/
[3]: https://www.ohwr.org/attachments/179/wbspec_b4.pdf
[4]: https://github.com/m-labs/nmigen/
[5]: https://www.veripool.org/wiki/verilator
[6]: http://riscv.org/software-tools/
[7]: https://github.com/riscv/riscv-compliance
[8]: https://www.sifive.com/boards
[9]: https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2019.08.0-x86_64-linux-ubuntu14.tar.gz
[10]: https://github.com/YosysHQ/yosys
