#!/usr/bin/env python3

import os
import yaml
import argparse
from string import Template
from nmigen import cli
from bellatrix.core import Bellatrix
from typing import Dict

logo = r'''--------------------------------------------------
     ___      _ _      _       _
    | _ ) ___| | |__ _| |_ _ _(_)_ __
    | _ \/ -_) | / _` |  _| '_| \ \ /
    |___/\___|_|_\__,_|\__|_| |_/_\_\

    A 32-bit RISC-V CPU based on nMigen
--------------------------------------------------'''
current_path = os.path.dirname(os.path.realpath(__file__))
cpu_variants = ['minimal', 'lite', 'standard', 'full', 'minimal_debug', 'custom']


def load_config(variant: str, configfile: str, verbose: bool) -> Dict:
    # default path to configurations
    if variant != 'custom':
        configfile  = '{}/configurations/bellatrix_{}.yml'.format(current_path, variant)
    elif configfile == '':
        raise RuntimeError('Configuration file empty for custom variant.')

    core_config = yaml.load(open(configfile).read(), Loader=yaml.Loader)

    config = {}

    # print configuration
    if verbose:
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


def generate_testbench(args, config):
    path = os.path.dirname(args.generate_file.name)
    icache_enable = config['icache_enable']
    dcache_enable = config['dcache_enable']
    data = dict(
        no_icache_assign='''assign iport__cti = 0;
    assign iport__bte = 0;''',
        no_icache_port='',
        no_dcache_assign='''assign dport__cti = 0;
    assign dport__bte = 0;''',
        no_dcache_port=''
    )

    if icache_enable:
        data['no_icache_assign'] = ''
        data['no_icache_port'] = '''.iport__cti         (iport__cti),
                        .iport__bte         (iport__bte),'''
    if dcache_enable:
        data['no_dcache_assign'] = ''
        data['no_dcache_port'] = '''.dport__cti         (dport__cti),
                        .dport__bte         (dport__bte),'''

    top_template_file = 'testbench/verilator/verilog/top_template'

    with open(top_template_file, 'r') as f:
        template = Template(f.read())

    template = template.substitute(data)

    with open(path + '/top.v', 'w') as f:
        f.write(template)


def generate_verilog(parser, args):
    # load configuration
    core_config = load_config(args.variant, os.path.realpath(args.config_file), args.verbose)

    # create the core
    cpu = Bellatrix(**core_config)
    ports = cpu.port_list()

    # generate the verilog file
    cli.main_runner(parser, args, cpu, name='bellatrix_core', ports=ports)
    # generate the testbench file
    generate_testbench(args, core_config)


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
