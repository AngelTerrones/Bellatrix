import argparse
from nmigen import cli
from bellatrix.core import Bellatrix
import bellatrix.configuration.configuration as cfg


def main():
    # parser: add options
    parser = argparse.ArgumentParser()

    # add (extra) arguments
    parser.add_argument("--config-file", type=str, help="configuration file", required=True)

    cli.main_parser(parser)
    args = parser.parse_args()

    # load the configuration file
    configuration = cfg.Configuration(args.config_file)

    # create the CPU
    cpu = Bellatrix(configuration)
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

    # run
    cli.main_runner(parser, args, cpu, name='bellatrix_core', ports=ports)


if __name__ == "__main__":
    main()
