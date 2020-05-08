#!/usr/bin/env python3

import os
import argparse
from nmigen import cli
from bellatrix.core import Bellatrix
from bellatrix.config.config import logo
from bellatrix.config.config import load_config
from testbench.verilator.generate_testbench import generate_testbench

current_path = os.path.dirname(os.path.realpath(__file__))
cpu_variants = ['minimal', 'lite', 'standard', 'full', 'minimal_debug', 'custom']
config_files = {variant: f'{current_path}/configurations/bellatrix_{variant}.yml' for variant in cpu_variants}


def generate_verilog(parser, args):
    # check arguments
    variant = args.variant
    if variant == 'custom':
        configfile = os.path.realpath(args.config_file)
        if configfile == '':
            raise RuntimeError('Configuration file empty for custom variant.')
    else:
        configfile = config_files[variant]

    # load configuration
    core_config = load_config(variant, configfile, args.verbose)

    # create the core
    cpu = Bellatrix(**core_config)
    ports = cpu.port_list()

    # generate the verilog file
    cli.main_runner(parser, args, cpu, name='bellatrix_core', ports=ports)
    # generate the testbench file
    if args.top_tb:
        try:
            path = os.path.dirname(args.generate_file.name)
            if path == '':
                path = './'
        except AttributeError:
            print('No verilog file has been generated. No tesbench is being generated')
        else:
            generate_testbench(core_config, path)


def main() -> None:
    class custom_formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(
        formatter_class=custom_formatter,
        description='''\033[1;33m{}\033[0m'''.format(logo)
    )

    # --------------------------------------------------------------------------
    # add arguments to parser
    parser.add_argument(
        '--variant',
        choices=cpu_variants,
        default='minimal',
        help='cpu variant'
    )
    parser.add_argument(
        '--config-file',
        default='',
        help='configuration file for custom variants'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='print the configuration file'
    )
    parser.add_argument(
        '--top-tb',
        action='store_true',
        help='generate testbench top file'
    )
    # --------------------------------------------------------------------------
    cli.main_parser(parser)
    args = parser.parse_args()

    if args.action == 'generate':
        generate_verilog(parser, args)
    else:
        print('No valid actions.')
        print('--------------------------------------------------')
        parser.print_help()


if __name__ == '__main__':
    main()
