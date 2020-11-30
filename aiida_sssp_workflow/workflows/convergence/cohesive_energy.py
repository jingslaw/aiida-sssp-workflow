# -*- coding: utf-8 -*-
"""
Convergence test on cohesive energy of a given pseudopotential
"""
from aiida.common import AttributeDict
from aiida.engine import WorkChain, ToContext, append_
from aiida import orm
from aiida.plugins import WorkflowFactory

CohesiveEnergyWorkChain = WorkflowFactory('sssp_workflow.cohesive_energy')

PARA_ECUTWFC_LIST = lambda: orm.List(list=[
    20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 110,
    120, 130, 140, 160, 180, 200
])


class ConvergenceCohesiveEnergyWorkChain(WorkChain):
    """WorkChain to converge test on cohisive energy of input structure"""
    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input('code',
                   valid_type=orm.Code,
                   help='The `pw.x` code use for the `PwCalculation`.')
        spec.input('pseudo',
                   valid_type=orm.UpfData,
                   required=True,
                   help='Pseudopotential to be verified')
        spec.input(
            'structure',
            valid_type=orm.StructureData,
            required=True,
            help='Ground state structure which the verification perform')
        spec.input('options',
                   valid_type=orm.Dict,
                   required=False,
                   help='Optional `options` to use for the `PwCalculations`.')
        spec.input_namespace('parameters', help='Para')
        spec.input('parameters.dual',
                   valid_type=orm.Int,
                   default=lambda: orm.Int(8),
                   help='dual value for ecutwfc/ecutrho pair.')
        spec.input('parameters.ecutwfc_list',
                   valid_type=orm.List,
                   default=PARA_ECUTWFC_LIST,
                   help='list of ecutwfc evaluate list.')
        spec.outline(
            cls.setup,
            cls.validate_structure,
            cls.run_ref,
            cls.run_all,
            cls.results,
        )
        spec.output(
            'output_parameters',
            valid_type=orm.Dict,
            required=True,
            help=
            'The output parameters include cohesive energy of the structure.')
        spec.output(
            'xy_data',
            valid_type=orm.XyData,
            required=True,
            help='The output XY data for plot use; the x axis is ecutwfc.')
        spec.exit_code(
            400,
            'ERROR_SUB_PROCESS_FAILED',
            message='The sub processes {pk} did not finish successfully.')

    def setup(self):
        pass

    def validate_structure(self):
        pass

    def get_inputs(self, ecutwfc, ecutrho):
        _PW_PARAS = orm.Dict( # pylint: disable=invalid-name
            dict={
                'SYSTEM': {
                    'degauss': 0.01,
                    'occupations': 'smearing',
                    'smearing': 'marzari-vanderbilt',
                    'ecutrho': ecutrho,
                    'ecutwfc': ecutwfc,
                },
            })
        inputs = AttributeDict({
            'code': self.inputs.code,
            'pseudo': self.inputs.pseudo,
            'structure': self.inputs.structure,
            'parameters': {
                'pw_bulk': _PW_PARAS,
                'pw_atom': _PW_PARAS,
                'kpoints_distance': orm.Float(0.15),
                'vacuum_length': orm.Float(12.0),
            },
        })

        return inputs

    def run_ref(self):
        """
        Running the calculation for the reference point
        hard code to 200Ry at the moment
        """
        ecutwfc = 200
        ecutrho = 200 * self.inputs.parameters.dual.value
        inputs = self.get_inputs(ecutwfc, ecutrho)

        running = self.submit(CohesiveEnergyWorkChain, **inputs)

        self.report(
            f'launching reference CohesiveEnergyWorkChain<{running.pk}>.')

        return ToContext(ref_workchain=running)

    def run_all(self):
        """
        Running the calculation for other points
        """
        ref_workchain = self.ctx.ref_workchain

        if not ref_workchain.is_finished_ok:
            self.report(
                f'Reference run of CohesiveEnergyWorkChain failed with exit status {ref_workchain.exit_status}'
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(
                pk=ref_workchain.pk)

        self.ctx.ref_energy = ref_workchain.outputs.output_parameters[
            'cohesive_energy']

        for ecutwfc in self.inputs.parameters.ecutwfc_list:
            ecutrho = ecutwfc * self.inputs.parameters.dual.value
            inputs = self.get_inputs(ecutwfc, ecutrho)

            workchain = self.submit(CohesiveEnergyWorkChain, **inputs)
            self.report(
                f'submitting cohesive energy evaluation {workchain.pk} on ecutwfc={ecutwfc} ecutrho={ecutrho}.'
            )
            self.to_context(children=append_(workchain))

    def results(self):
        """
        doc
        """
        import numpy as np

        pks = [
            child.pk for child in self.ctx.children if not child.is_finished_ok
        ]
        if pks:
            # TODO failed only when points are not enough < 80%
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED.format(pk=pks)

        success_child = [
            child for child in self.ctx.children if child.is_finished_ok
        ]
        cohesive_energies = []
        relative_values = []
        ecutwfc_list = []
        ecutrho_list = []

        ref_energy = self.ctx.ref_energy
        for child in success_child:
            ecutwfc = child.inputs.parameters__pw_bulk['SYSTEM']['ecutwfc']
            ecutrho = child.inputs.parameters__pw_bulk['SYSTEM']['ecutrho']
            energy = child.outputs.output_parameters['cohesive_energy']
            relative_value = (energy -
                              ref_energy) / ref_energy * 100.0  # unit %
            ecutwfc_list.append(ecutwfc)
            ecutrho_list.append(ecutrho)

            cohesive_energies.append(energy)
            relative_values.append(relative_value)

        xy_data = orm.XyData()
        xy_data.set_x(np.array(ecutwfc_list), 'wavefunction cutoff', 'Rydberg')
        xy_data.set_y(np.array(relative_values),
                      'Relative values of cohesive energy', '%')

        output_parameters = orm.Dict(
            dict={
                'ecutwfc_list': ecutwfc_list,
                'ecutrho_list': ecutrho_list,
                'cohesive_energies': cohesive_energies,
                'relative_values': relative_values,
                'cutoff_unit': 'Ry',
                'cohesive_energy_unit': 'eV/atom',
                'relative_unit': '%'
            })
        self.out('output_parameters', output_parameters.store())
        self.out('xy_data', xy_data.store())
