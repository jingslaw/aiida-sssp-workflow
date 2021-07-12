#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Running delta factor workchain example
"""
import os

from aiida import orm

from aiida.plugins import WorkflowFactory, DataFactory
from aiida.engine import run_get_node

UpfData = DataFactory('pseudo.upf')
DeltaFactorWorkChain = WorkflowFactory('sssp_workflow.delta_factor')

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_static')

def run_delta(code, upf):
    inputs = {
        'code': code,
        'pseudo': upf,
        'protocol': orm.Str('test'),
        'options': orm.Dict(
                dict={
                    'resources': {
                        'num_machines': 1
                    },
                    'max_wallclock_seconds': 1800 * 3,
                    'withmpi': False,
                }),
        'parallelization': orm.Dict(dict={}),
        'clean_workdir': orm.Bool(True),
    }

    res, node = run_get_node(DeltaFactorWorkChain, **inputs)
    return res, node


if __name__ == '__main__':
    from aiida.orm import load_code
    from aiida import load_profile

    load_profile('sssp-dev')
    code = load_code('pw64@localhost')

    upf_sg15 = {}
    # sg15/Si_ONCV_PBE-1.2.upf
    pp_name = 'Si_ONCV_PBE-1.2.upf'
    pp_path = os.path.join(STATIC_DIR, pp_name)
    with open(pp_path, 'rb') as stream:
        pseudo = UpfData(stream)
        upf_sg15['si'] = pseudo

    for element, upf in upf_sg15.items():
        res, node = run_delta(code, upf)
        node.description = f'sg15/{element}'
        print(node)

    # upf_wt = {}
    # # WT/La.GGA-PBE-paw-v1.0.UPF
    # pp_name = 'La.GGA-PBE-paw-v1.0.UPF'
    # pp_path = os.path.join(STATIC_DIR, pp_name)
    # with open(pp_path, 'rb') as stream:
    #     pseudo = UpfData(stream)
    #     upf_wt['La'] = pseudo

    # for element, upf in upf_wt.items():
    #     res, node = run_delta(code, upf)
    #     node.description = f'WT/{element}-PBE'
    #     print(node)


    # upf_mag = {}
    # # MAG/O_ONCV_PBE-1.2.upf
    # pp_name = 'O_ONCV_PBE-1.2.upf'
    # pp_path = os.path.join(STATIC_DIR, pp_name)
    # with open(pp_path, 'rb') as stream:
    #     pseudo = UpfData(stream)
    #     upf_mag['O'] = pseudo

    # for element, upf in upf_mag.items():
    #     res, node = run_delta(code, upf)
    #     node.description = f'MAG/SG15/{element}'
    #     print(node)
