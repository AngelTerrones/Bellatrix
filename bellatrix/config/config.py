import yaml
from typing import Dict

logo = r'''--------------------------------------------------
     ___      _ _      _       _
    | _ ) ___| | |__ _| |_ _ _(_)_ __
    | _ \/ -_) | / _` |  _| '_| \ \ /
    |___/\___|_|_\__,_|\__|_| |_/_\_\

    A 32-bit RISC-V CPU based on nMigen
--------------------------------------------------'''

header = '''\033[1;33m{logo}\033[0m

\033[0;32mConfiguration\033[0;0m
Variant name: {variant}
Path config file: {configfile}

\033[0;32mBuild parameters\033[0;0m'''


def load_config(variant: str, configfile: str, verbose: bool) -> Dict:
    core_config = yaml.load(open(configfile).read(), Loader=yaml.Loader)
    config      = {}

    for key, item in core_config.items():
        if isinstance(item, dict):
            for k2, i2 in item.items():
                config['{}_{}'.format(key, k2)] = i2
        else:
            config[key] = item

    if verbose:
        print(header.format(logo=logo, variant=variant, configfile=configfile))
        for key, item in core_config.items():
            if isinstance(item, dict):
                print(f'{key}:')
                for k2, i2 in item.items():
                    if k2 in ('reset_address', 'start', 'end'):
                        print(f'- {k2}: {hex(i2)}')
                    else:
                        print(f'- {k2}: {i2}')
            else:
                print(f'{key}: {item}')
        print('--------------------------------------------------')

    return config
