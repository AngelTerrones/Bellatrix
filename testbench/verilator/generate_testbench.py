import os
from typing import Dict
from string import Template

current_path = os.path.dirname(os.path.realpath(__file__))
top_template_file = f'{current_path}/verilog/top_template'


def generate_testbench(config: Dict, path: str) -> None:
    print(f'\033[0;32mTestbench top file\033[0;0m: {path}/top.v')
    icache_enable = config['icache_enable']
    dcache_enable = config['dcache_enable']

    data = dict(
        icache='',
        dcache=''
    )

    if icache_enable:
        data['icache'] = '`define ICACHE'
    if dcache_enable:
        data['dcache'] = '`define DCACHE'

    # create the template
    with open(top_template_file, 'r') as f:
        template = Template(f.read())

    top = template.substitute(data)

    with open(path + '/top.v', 'w') as f:
        f.write(top)
    print('--------------------------------------------------')
