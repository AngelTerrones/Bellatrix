#!/usr/bin/env python3

import os
import glob
import sys
import argparse
import subprocess
from subprocess import CalledProcessError
from nmigen.back import verilog
from nmigen.hdl.ir import Fragment
from bellatrix.gateware.core import Bellatrix
from bellatrix.config.config import logo
from bellatrix.config.config import load_config
from bellatrix.config.config import cpu_variants
from bellatrix.config.config import config_files
from bellatrix.verilator.generate import generate_makefile
from bellatrix.verilator.generate import generate_testbench


def need_rebuild(bfolder: str):
    root  = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(f'{root}/bellatrix/gateware/**/*.py', recursive=True)
    if not os.path.exists(f'{bfolder}/bellatrix_core.v'):
        return True
    ref   = os.stat(f'{bfolder}/bellatrix_core.v').st_mtime_ns

    for file in files:
        tmp = os.stat(file).st_mtime_ns
        if tmp > ref:
            return True

    return False


def CPU_to_verilog(core_config: dict, vfile: str):
    cpu = Bellatrix(**core_config)
    ports = cpu.port_list()

    # generate the verilog file
    fragment = Fragment.get(cpu, None)
    output = verilog.convert(fragment, name='bellatrix_core', ports=ports)
    try:
        with open(vfile, 'w') as f:
            f.write(output)
    except EnvironmentError as error:
        print(f"Error: {error}. Check if the output path exists.", file=sys.stderr)


def generate_cpu_verilog(args):
    # load configuration
    core_config = load_config(args.variant, args.config, args.verbose)
    CPU_to_verilog(core_config, args.filename)


def build_testbench(args):
    for variant in args.variant:
        path = f'build/{variant}'

        # check if the testbench has been built
        rebuild = need_rebuild(path)

        if (os.path.exists(f'{path}/core.exe') and not rebuild):
            print('Testbench up-to-date. Skipping.')
            return

        os.makedirs(path, exist_ok=True)

        # generate verilog
        core_config = load_config(variant, args.config, False)
        CPU_to_verilog(core_config, f'{path}/bellatrix_core.v')

        # generate testbench and makefile
        generate_testbench(core_config, path)
        generate_makefile(path)
        # get the config file
        if variant == 'custom':
            configfile = args.config
        else:
            configfile = config_files[variant]

        # run make
        os.environ['BCONFIG'] = configfile
        subprocess.check_call(f'make -C {path} -j$(nproc)', shell=True, stderr=subprocess.STDOUT)


def run_compliance(args):
    # build the testbench
    build_testbench(args)

    riscv_path = os.environ.get('RVGCC_PATH')
    if riscv_path is None:
        raise EnvironmentError('Environment variable "RVGCC_PATH" is undefined.')

    os.environ['RISCV_PREFIX'] = f'{riscv_path}/riscv64-unknown-elf-'

    variant_msg = []
    for variant in args.variant:
        os.environ['TARGET_FOLDER'] = os.path.abspath(f'build/{variant}')
        isa_msg = []
        for isa in args.isa:
            try:
                subprocess.check_call(f'make -C {args.rvc} variant RISCV_TARGET=bellatrix RISCV_DEVICE=rv32i RISCV_ISA={isa}',
                                      shell=True, stderr=subprocess.STDOUT)
                isa_msg.append(f'{isa} test ended sucessfully.')
            except CalledProcessError as error:
                print(f"Error: {error}", file=sys.stderr)
                isa_msg.append(f'{isa} test with errors.')

        variant_msg.append(isa_msg)

    print('\n------------------------------------------------------------')
    print('Results:')
    print('------------------------------------------------------------')
    for variant, msg in zip(args.variant, variant_msg):
        print(f'{variant} configuration:')
        for tmp in msg:
            print(f'\t{tmp}')
    print('------------------------------------------------------------')


def main() -> None:
    class custom_formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(formatter_class=custom_formatter,
                                     description='''\033[1;33m{}\033[0m'''.format(logo))

    # Actions
    p_action = parser.add_subparsers(dest='action', help='Available commands')
    # --------------------------------------------------------------------------
    # Generate core verilog
    p_generate_cpu = p_action.add_parser('generate_cpu', help='Generate CPU Verilog from the design')
    p_generate_cpu.add_argument('filename', metavar="FILE",
                                help="Write generated verilog to FILE")
    p_generate_cpu.add_argument('--variant', choices=cpu_variants, required=True,
                                help='CPU type')
    p_generate_cpu.add_argument('--config',
                                help='Configuration file for custom variants')
    p_generate_cpu.add_argument('--verbose', action='store_true',
                                help='Print the configuration file')
    # --------------------------------------------------------------------------
    # build verilator testbench
    p_buildtb = p_action.add_parser('buildtb', help='Build the Verilator simulator')
    p_buildtb.add_argument('--variant', choices=cpu_variants, nargs='+', required=True,
                           help='CPU type')
    p_buildtb.add_argument('--config',
                           help='Configuration file for custom variants')
    # --------------------------------------------------------------------------
    # run compliance test
    p_compliance = p_action.add_parser('compliance', help='Run the RISC-V compliance test')
    p_compliance.add_argument('--rvc', required=True,
                              help='Path to riscv-compliance')
    p_compliance.add_argument('--variant', choices=cpu_variants, nargs='+', required=True,
                              help='CPU type')
    p_compliance.add_argument('--config',
                              help='Configuration file for custom variants')
    p_compliance.add_argument('--isa', choices=['rv32i', 'rv32im', 'rv32mi', 'rv32ui', 'rv32Zicsr', 'rv32Zifencei'],
                              nargs='+', required=True, help='Available compliance tests',)
    # --------------------------------------------------------------------------
    args = parser.parse_args()
    # --------------------------------------------------------------------------
    # execute
    if args.action == 'generate_cpu':
        generate_cpu_verilog(args)
    elif args.action == 'buildtb':
        build_testbench(args)
    elif args.action == 'compliance':
        run_compliance(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
