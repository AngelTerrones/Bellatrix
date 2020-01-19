#!/usr/bin/env python3

import os
import yaml
import argparse
from nmigen import cli
from bellatrix.core import Bellatrix
from typing import Dict

logo = r'''--------------------------------------------------
     ___      _ _      _       _
    | _ ) ___| | |__ _| |_ _ _(_)_ __
    | _ \/ -_) | / _` |  _| '_| \ \ /
    |___/\___|_|_\__,_|\__|_| |_/_\_\\

    A 32-bit RISC-V CPU based on nMigen
--------------------------------------------------'''
current_path = os.path.dirname(os.path.realpath(__file__))
cpu_variants = ['minimal', 'lite', 'standard', 'full', 'custom']


def load_config(variant: str, configfile: str) -> Dict:
    # default path to configurations
    if variant != 'custom':
        configfile  = '{}/configurations/bellatrix_{}.yml'.format(current_path, variant)
    elif configfile == '':
        raise RuntimeError('Configuration file empty for custom variant.')

    core_config = yaml.load(open(configfile).read(), Loader=yaml.Loader)

    config = {}

    # print configuration
    print('''\033[1;33m{}\033[0m

\033[0;32mConfiguration\033[0;0m
Variant name: {}
Path config file: {}

\033[0;32mBuild parameters\033[0;0m'''.format(logo, variant, configfile))

    # translate and print parameters
    for key, item in core_config.items():
        if isinstance(item, dict):
            print(f'{key}:')
            for k2, i2 in item.items():
                config['{}_{}'.format(key, k2)] = i2
                if isinstance(i2, int) and not isinstance(i2, bool):
                    print(f'- {k2}: {i2} ({hex(i2)})')
                else:
                    print(f'- {k2}: {i2}')
        else:
            config[key] = item
            print(f'{key}: {item}')
    print('--------------------------------------------------')

    return config


def generate_verilog(parser, args):
    # load configuration
    core_config = load_config(args.variant, os.path.realpath(args.config_file))

    # create the core
    cpu = Bellatrix(**core_config)
    ports = [
        # instruction port
        cpu.iport.addr,
        cpu.iport.dat_w,
        cpu.iport.sel,
        cpu.iport.we,
        cpu.iport.cyc,
        cpu.iport.stb,
        cpu.iport.cti,
        cpu.iport.bte,
        cpu.iport.dat_r,
        cpu.iport.ack,
        cpu.iport.err,
        # data port
        cpu.dport.addr,
        cpu.dport.dat_w,
        cpu.dport.sel,
        cpu.dport.we,
        cpu.dport.cyc,
        cpu.dport.stb,
        cpu.dport.cti,
        cpu.dport.bte,
        cpu.dport.dat_r,
        cpu.dport.ack,
        cpu.dport.err,
        # exceptions
        cpu.external_interrupt,
        cpu.timer_interrupt,
        cpu.software_interrupt
    ]
    if core_config['icache_enable']:
        ports += [
            cpu.i_snoop.addr,
            cpu.i_snoop.we,
            cpu.i_snoop.valid,
            cpu.i_snoop.ack,
        ]
    if core_config['dcache_enable']:
        ports += [
            cpu.d_snoop.addr,
            cpu.d_snoop.we,
            cpu.d_snoop.valid,
            cpu.d_snoop.ack,
        ]

    # generate the verilog file
    cli.main_runner(parser, args, cpu, name='bellatrix_core', ports=ports)


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
