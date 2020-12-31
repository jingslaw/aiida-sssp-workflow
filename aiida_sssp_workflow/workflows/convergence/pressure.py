# -*- coding: utf-8 -*-
"""
Convergence test on cohesive energy of a given pseudopotential
"""
from aiida.engine import calcfunction
from aiida import orm
from aiida.plugins import WorkflowFactory

from aiida_sssp_workflow.utils import update_dict
from .base import BaseConvergenceWorkChain

PressureWorkChain = WorkflowFactory('sssp_workflow.pressure_evaluation')

PARA_ECUTWFC_LIST = lambda: orm.List(list=[
    20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 110,
    120, 130, 140, 160, 180, 200
])

PARA_ECUTRHO_LIST = lambda: orm.List(list=[
    160, 200, 240, 280, 320, 360, 400, 440, 480, 520, 560, 600, 640, 680, 720,
    760, 800, 880, 960, 1040, 1120, 1280, 1440, 1600
])


def helper_get_volume_from_pressure_birch_murnaghan(P, V0, B0, B1):
    """
    Knowing the pressure P and the Birch-Murnaghan equation of state
    parameters, gets the volume the closest to V0 (relatively) that is
    such that P_BirchMurnaghan(V)=P

    retrun unit is (%)
    """
    import numpy as np

    # coefficients of the polynomial in x=(V0/V)^(1/3) (aside from the
    # constant multiplicative factor 3B0/2)
    polynomial = [
        3. / 4. * (B1 - 4.), 0, 1. - 3. / 2. * (B1 - 4.), 0,
        3. / 4. * (B1 - 4.) - 1., 0, 0, 0, 0, -2 * P / (3. * B0)
    ]
    V = min([
        V0 / (x.real**3)
        for x in np.roots(polynomial) if abs(x.imag) < 1e-8 * abs(x.real)
    ],
            key=lambda V: abs(V - V0) / float(V0))

    return abs(V - V0) / V0 * 100


@calcfunction
def helper_pressure_difference(input_parameters: orm.Dict,
                               ref_parameters: orm.Dict, V0: orm.Float,
                               B0: orm.Float, B1: orm.Float) -> orm.Dict:
    """
    doc
    """
    res_pressure = input_parameters['hydrostatic_stress']
    ref_pressure = ref_parameters['hydrostatic_stress']
    absolute_diff = abs(res_pressure - ref_pressure)
    relative_diff = helper_get_volume_from_pressure_birch_murnaghan(
        absolute_diff, V0.value, B0.value, B1.value)

    return orm.Dict(
        dict={
            'relative_diff': relative_diff,
            'absolute_diff': absolute_diff,
            'absolute_unit': 'GPascal',
            'relative_unit': '%'
        })


class ConvergencePressureWorkChain(BaseConvergenceWorkChain):
    """WorkChain to converge test on pressure of input structure"""

    # hard code parameters of evaluate workflow
    _DEGUASS = 0.00735
    _OCCUPATIONS = 'smearing'
    _SMEARING = 'marzari-vanderbilt'
    _KDISTANCE = 0.15
    _CONV_THR = 1e-10

    # hard code parameters of convergence workflow
    _TOLERANCE = 1e-1
    _CONV_THR_CONV = 1e-1
    _CONV_WINDOW = 3

    _ABSOLUTE_UNIT = 'GPascal'

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input('code',
                   valid_type=orm.Code,
                   help='The `pw.x` code use for the `PwCalculation`.')
        spec.input(
            'parameters.v0_b0_b1',
            valid_type=orm.Dict,
            help=
            'birch murnaghan fit results used in residual volume evaluation.')

    def get_create_process(self):
        return PressureWorkChain

    def get_evaluate_process(self):
        return helper_pressure_difference

    def get_parsed_results(self):
        return {
            'absolute_diff':
            ('The absolute residual pressure difference', 'GPascal'),
            'relative_diff':
            ('The relative residual pressure difference', '%'),
        }

    def get_converge_y(self):
        return 'relative_diff', '%'

    def get_create_process_inputs(self):
        _PW_PARAS = {   # pylint: disable=invalid-name
            'SYSTEM': {
                'degauss': self._DEGUASS,
                'occupations': self._OCCUPATIONS,
                'smearing': self._SMEARING,
            },
            'ELECTRONS': {
                'conv_thr': self._CONV_THR,
            },
        }

        inputs = {
            'code': self.inputs.code,
            'pseudos': self.ctx.pseudos,
            'structure': self.ctx.structure,
            'parameters': {
                'pw':
                orm.Dict(
                    dict=update_dict(_PW_PARAS, self.ctx.base_pw_parameters)),
                'kpoints_distance':
                orm.Float(self._KDISTANCE),
            },
        }

        return inputs

    def get_evaluate_process_inputs(self):
        ref_workchain = self.ctx.ref_workchain
        V0_B0_B1 = self.inputs.parameters.v0_b0_b1  # pylint: disable=invalid-name

        res = {
            'ref_parameters': ref_workchain.outputs.output_parameters,
            'V0': orm.Float(V0_B0_B1['V0']),
            'B0': orm.Float(V0_B0_B1['B0']),
            'B1': orm.Float(V0_B0_B1['B1']),
        }

        return res

    def get_output_input_mapping(self):
        res = orm.Dict(dict={'output_parameters': 'input_parameters'})
        return res
