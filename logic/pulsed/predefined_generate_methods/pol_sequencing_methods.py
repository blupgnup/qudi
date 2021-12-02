import numpy as np
from logic.pulsed.pulse_objects import PulseBlock, PulseBlockEnsemble, PulseSequence
from logic.pulsed.pulse_objects import PredefinedGeneratorBase

from logic.pulsed.sampling_function_defs.sampling_functions_nvision import EnvelopeMethods
from logic.pulsed.predefined_generate_methods.basic_methods_polarization_nvision import NVisionPolarizationGenerator

from logic.pulsed.sampling_functions import DDMethods
from core.util.helpers import csv_2_list


OFFSET_TAU_MFL_SEQMODE = 3      # number of sequence elements in front of ramseys
DELTA_TAU_I_MFL_SEQMODE = 2     # separation between different ramseys in sequence
OFFSET_TAU_MFL_LIN_SEQMODE = 1      # number of sequence elements in front of sequence segments
DELTA_TAU_I_MFL_LIN_SEQMODE = 2     # separation between different sequence segments in sequence
SEG_I_IDLE_SEQMODE = 2          # idx of idle segment
SEG_I_EPOCH_DONE_SEQMODE = 3    # idx of epoch done segment


class MFLPatternJump_Generator(PredefinedGeneratorBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # holds description while generating all sequence elements
        # NOT the actual seqtable written to the AWG
        self._seqtable = None
        self._seqtable_counter = 0
        self._jumptable = None
        self._jumptable_address = 1 # all low (0000 0000) shouldn't be a valid address
        self.init_seqtable()
        self.init_jumptable()

        self.gen_nvision = NVisionPolarizationGenerator(*args, **kwargs)


    def _add_to_seqtable(self, name, blocks, ensembles, seq_params):
        self._seqtable['blocks'] += blocks
        self._seqtable['ensembles'] += ensembles
        self._seqtable['seq_params'].append([name, seq_params])
        self._seqtable_counter += 1

    def _add_to_jumptable(self, name):
        """ Call BEFORE _add_to_seqtable, as this will iterate _seqtable_counter """
        self._jumptable['name'].append(name)
        self._jumptable['idx_seqtable'].append(self._seqtable_counter)
        self._jumptable['jump_address'].append(self._seqtable_counter)
        # for AWG8190 no seperate jumptable -> jump addresses are seqtable ids
        self._jumptable_address += 1

    def init_seqtable(self):
        self._seqtable = {'blocks': [], 'ensembles': [], 'seq_params': []}
        self._seqtable_counter = 0

    def init_jumptable(self):
        self._jumptable = {'name': [], 'idx_seqtable': [], 'jump_address': []}
        self._jumptable_address = 0

    def _seqtable_to_result(self):
        # as needed from sequencer
        return self._seqtable['blocks'], self._seqtable['ensembles'], self._seqtable['seq_params']

    def _get_current_seqtable_idx(self):
        # only valid while iterating through generation of sequence
        return self._seqtable_counter

    def _get_current_jumptable_address(self):
        # only valid while iterating through generation of sequence
        return self._seqtable_counter

    def _add_ensemble_to_seqtable(self, blocks, ensemble, name, seq_params=None):
        cur_seq_params = self._get_default_seq_params(seq_params)
        self._add_to_seqtable(name, blocks, ensemble, cur_seq_params)

    def generate_ppol_2x_propi(self, name="ppol_2x_propi", n_pol=100, m_read_step=20,
                               tau_ppol=50e-9, order_ppol=1, alternating=True,
                               env_type=EnvelopeMethods.rectangle, order_P=1
                               ):

        cur_name = 'ppol_init_up'
        cur_blocks, cur_ensembles, _ = self._create_single_ppol(cur_name, tau_ppol, order_ppol, 'up',
                                                                alternating=False, add_gate_ch='',
                                                                env_type=env_type, order_P=order_P
                                                                )
        blocks, enembles, sequences = self.generic_ppol_propi(cur_name, ov_name=name,
                                                              pol_blocks=cur_blocks, pol_ensemble=cur_ensembles,
                                                              n_pol=n_pol, m_read_step=m_read_step, tau_ppol=tau_ppol,
                                                              order_ppol=order_ppol, alternating=alternating,
                                                              pol_read='down',
                                                              env_type=env_type, order_P=order_P
                                                              )

        return blocks, enembles, sequences

    def generate_rnovel_ppol_propi(self, name='rnovel_ppol_propi',
                                   dd_mol_tau=0.5e-6, dd_mol_order=10, dd_mol_ampl=0.1, dd_mol_type=DDMethods.CPMG,
                                   dd_t_rabi_rect=0e-9,
                                   n_pol=100, m_read_step=20, tau_ppol=50e-9, order_ppol=1,
                                   env_type=EnvelopeMethods.rectangle, order_P=1,
                                   alternating=True):

        # Hovav (2018): RNOVEL
        cur_name = 'rnovel_init_up' # hopefully up

        phases_dress2 = str([90] * dd_mol_type.suborder)[1:-1]
        common_t_rabi = self.rabi_period

        # make mollow part non-shaped again
        shaped_pmollow = dd_t_rabi_rect <= 0e-9
        if not shaped_pmollow:
            self.log.info(f"Generating rnovel with rect pulses, ppol_propi with {env_type}")
        # overwrite temporarily the protected common rabi period
        self._PredefinedGeneratorBase__sequencegeneratorlogic.generation_parameters['rabi_period'] = dd_t_rabi_rect \
            if not shaped_pmollow else self.rabi_period
        env_type_mol = env_type if shaped_pmollow else EnvelopeMethods.rectangle
        env_orderP_mol = order_P if shaped_pmollow else EnvelopeMethods.rectangle


        cur_blocks, cur_ensembles, _ = self._create_single_dd_mollow(name=cur_name, tau=dd_mol_tau, ampl_mol=dd_mol_ampl,
                                                                     dd_type=dd_mol_type, dd_order=dd_mol_order,
                                                                     f_mol=0e6, phase_mod=phases_dress2,
                                                                     env_type=env_type_mol, order_P=env_orderP_mol,
                                                                     alternating=False)
        self._PredefinedGeneratorBase__sequencegeneratorlogic.generation_parameters['rabi_period'] = common_t_rabi


        blocks, enembles, sequences = self.generic_ppol_propi(cur_name, ov_name=name,
                                                              pol_blocks=cur_blocks, pol_ensemble=cur_ensembles,
                                                              n_pol=n_pol, m_read_step=m_read_step, tau_ppol=tau_ppol,
                                                              order_ppol=order_ppol,
                                                              env_type=env_type, order_P=order_P,
                                                              alternating=alternating,
                                                              pol_read='down')

        return blocks, enembles, sequences

    def generate_ise_ppol_propi(self, name='ise_ppol_propi',
                                t_ise=1e-6, df_mw_sweep=10e6,
                                mw_sweep_speed=3e12, amp_mw_sweep=0.25,
                                   n_pol=100, m_read_step=20, tau_ppol=50e-9, order_ppol=1, ppol_read_dir='up',
                                   env_type=EnvelopeMethods.rectangle, order_P=1,
                                   alternating=True):

        cur_name = 'ise_init_down'

        cur_blocks, cur_ensembles, _ = self._create_single_ise(name=cur_name, t_ise=t_ise, f_res=self.microwave_frequency,
                                                               df_mw_sweep=df_mw_sweep, mw_sweep_speed=mw_sweep_speed,
                                                               amp_mw_sweep=amp_mw_sweep, both_sweep_polarities=False)

        blocks, enembles, sequences = self.generic_ppol_propi(cur_name, ov_name=name,
                                                              pol_blocks=cur_blocks, pol_ensemble=cur_ensembles,
                                                              n_pol=n_pol, m_read_step=m_read_step, tau_ppol=tau_ppol,
                                                              order_ppol=order_ppol,
                                                              env_type=env_type, order_P=order_P,
                                                              alternating=alternating,
                                                              pol_read=ppol_read_dir)

        return blocks, enembles, sequences


    def generic_ppol_propi(self, pol_name="generic_pol", ov_name=None, pol_blocks=None, pol_ensemble=None,
                           n_pol=100, m_read_step=20, tau_ppol=50e-9,
                           order_ppol=1, pol_read='down',
                           env_type=EnvelopeMethods.rectangle, order_P=1, alternating=True):
        """
        Adds a PulsePol Propi readout to some generic polarization sequence.
        """
        # for linear sequencers like Keysight AWG
        # self.init_jumptable()  # jumping currently not needed
        self.init_seqtable()
        general_params = locals()
        name = f"{pol_name}_ppol_propi" if not ov_name else ov_name

        # read polarization has to come first
        # the laser extraction is based on the laser_rising_bins
        # which are counted in the order of the sequence step
        cur_name = 'ppol_read'
        cur_blocks, cur_ensembles, _ = self._create_single_ppol(cur_name, tau_ppol, order_ppol, pol_read,
                                                                env_type=env_type, order_P=order_P,
                                                                alternating=alternating)
        self._add_ensemble_to_seqtable(cur_blocks, cur_ensembles, cur_name,
                                       seq_params={'repetitions': int(m_read_step - 1)})
        # init polarization
        if pol_blocks and pol_ensemble:
            self._add_ensemble_to_seqtable(pol_blocks, pol_ensemble, pol_name,
                                           seq_params={'repetitions': int(n_pol - 1)})

        # sync trigger for start readout
        sync_name = 'sync_trig'
        sync_blocks, sync_ensembles, _ = self._create_generic_trigger(sync_name, self.sync_channel)
        self._add_ensemble_to_seqtable(sync_blocks, sync_ensembles, sync_name,
                                       seq_params={'repetitions': int(0)})

        all_blocks, all_ensembles, ensemble_list = self._seqtable_to_result()
        sequence = PulseSequence(name=name, ensemble_list=ensemble_list, rotating_frame=False)

        # get length of ppol_read ensemble
        idx_read = 0
        fastcounter_count_length = int(m_read_step) * self._get_ensemble_count_length(all_ensembles[idx_read],
                                                                                      created_blocks=all_blocks)

        contr_var = np.arange(m_read_step) + 1
        n_lasers = len(contr_var)
        n_lasers = 2 * n_lasers if alternating else n_lasers
        n_phys_lasers = n_lasers + n_pol
        laser_ignore = np.arange(n_lasers, n_phys_lasers, 1)

        self.log.debug(f"Setting fastcounter count length to {1e6*fastcounter_count_length:.3f} us "
                       f"for {n_lasers} read lasers from ensemble {all_ensembles[idx_read].name}")

        self._add_metadata_to_settings(sequence, alternating=alternating, created_blocks=list(),
                                       laser_ignore_list=list(laser_ignore),
                                       controlled_variable=contr_var, units=('', ''), labels=('Depol. step', 'Signal'),
                                       number_of_lasers=n_lasers,
                                       counting_length=fastcounter_count_length)

        return all_blocks, all_ensembles, [sequence]

    def _swap_pos(self, arr, pos1, pos2):
        """
        Swap pos between a<->b in 1d or 2d array likes.
        :param array:
        :param pos1: Flattened index a
        :param pos2: Flattened index b
        :return:
        """

        shape_orig = np.asarray(arr).shape
        arr_flat = np.asarray(arr).flatten()
        arr_flat[pos1], arr_flat[pos2] = arr_flat[pos2], arr_flat[pos1]
        arr = arr_flat.reshape(shape_orig)

        return arr

    def _create_init_laser_pulses(self, general_params, name='laser_wait'):
        created_blocks = []
        created_ensembles = []

        created_blocks_tmp, created_ensembles_tmp, created_sequences_tmp = \
            self._create_laser_wait(name=name, laser_length=general_params['laser_length'],
                                    wait_length=general_params['wait_length']
                                    )
        created_blocks += created_blocks_tmp
        created_ensembles += created_ensembles_tmp

        # todo: check if save
        #if general_params['alternating']:
        #    raise NotImplemented("Look into repetitive_readout_methods.py if needed")

        return created_blocks, created_ensembles

    # todo: inherit shared methods
    def _create_laser_wait(self, name='laser_wait', laser_length=500e-9, wait_length=1e-6):
        """ Generates Laser pulse and waiting (idle) time.

        @param str name: Name of the PulseBlockEnsemble
        @param float length: laser duration in seconds
        @param float amp: In case of analogue laser channel this value will be the laser on voltage.

        @return object: the generated PulseBlockEnsemble object.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()
        # create the laser element
        laser_element = self._get_laser_gate_element(length=laser_length, increment=0)
        waiting_element = self._get_idle_element(length=wait_length, increment=0.0)

        # Create the element list
        block = PulseBlock(name=name)
        block.append(laser_element)
        block.append(waiting_element)
        #block.extend(laser_element, waiting_element)
        created_blocks.append(block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((block.name, 0))
        # add metadata to invoke settings
        block_ensemble = self._add_metadata_to_settings(block_ensemble, created_blocks=created_blocks, alternating=False, number_of_lasers=0) # todo: check 0 or 1 laser?
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences


    def _get_index_of_ramsey(self, tau, tau_array, linear_sequencer=False):
        """
        Ramseys or equivalent (1 parameter) sequences have taus as described by tau_array.
        Get the sequence index of the tau that is closest to given first tau value.
        :param tau:
        :param tau_array:
        :return:
        """
        idx, val = self._find_nearest(tau_array, tau)
        if not linear_sequencer:
            idx_in_sequence = 1 + OFFSET_TAU_MFL_SEQMODE + DELTA_TAU_I_MFL_SEQMODE * idx
        else:
            idx_in_sequence = 1 + OFFSET_TAU_MFL_LIN_SEQMODE + DELTA_TAU_I_MFL_LIN_SEQMODE * idx
        return int(idx_in_sequence), val

    def _get_index_of_xy8(self, tau, n_xy8, tau_n_array, idx_of_seqtable=True, is_linear_sequencer=False):
        """
        XY8 or equivalent (2 parameter) sequences have taus as described by tau_array.
        Get the sequence index of the tau that is closest to given first tau value.
        :param tau: looked for tau
        :param n_xy8: looked for n_xy8
        :param tau_n_array: meshgrid like. tau_n[0][i_t,j_n] -> tau; tau_n[1][i_t,j_n] -> n_xy8
        :return:
        """
        # assumes tau_n_array is well spaced
        idx_t, val_t = self._find_nearest(tau_n_array[0][0,:], tau)
        idx_n, val_n = self._find_nearest(tau_n_array[1][:,0], n_xy8)
        len_t = len(tau_n_array[0][0,:])

        idx = len_t * idx_n + idx_t

        if not is_linear_sequencer:
            idx_in_sequence = 1 + OFFSET_TAU_MFL_SEQMODE + DELTA_TAU_I_MFL_SEQMODE * idx
        else:
            idx_in_sequence = 1 + OFFSET_TAU_MFL_LIN_SEQMODE + DELTA_TAU_I_MFL_LIN_SEQMODE * idx

        if idx_of_seqtable:
            return int(idx_in_sequence), val_t, val_n
        else:
            return int(idx), val_t, val_n

    def _find_nearest(self, array, value):
        array = np.asarray(array)
        idx = (np.abs(array - value)).argmin()
        return idx, array[idx]

    def _get_default_seq_params(self, overwrite_param_dict=None):
        """
        default params for a sequence segement for MFL
        see pulse_objects.py::PulseSequence() for explanation of params
        :param seq_para_dict:
        :return:
        """

        if overwrite_param_dict is None:
            seq_para_dict = {}
        else:
            seq_para_dict = overwrite_param_dict

        if 'event_trigger' not in seq_para_dict:
            seq_para_dict['event_trigger'] = 'OFF'
        if 'event_jump_to' not in seq_para_dict:
            seq_para_dict['event_jump_to'] = 0
        if 'wait_for' not in seq_para_dict:
            seq_para_dict['wait_for'] = 'OFF'
        if 'repetitions' not in seq_para_dict:
            seq_para_dict['repetitions'] = 0
        if 'go_to' not in seq_para_dict:
            seq_para_dict['go_to'] = 0
        return seq_para_dict

    def _create_generic_idle(self, name='idle'):
        created_blocks = []
        created_ensembles = []
        created_sequences = []

        idle_element = self._get_idle_element(length=1e-9, increment=0.0)
        block = PulseBlock(name=name)
        block.append(idle_element)

        self._extend_to_min_samples(block)

        # prepare return vals
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((block.name, 0))
        created_blocks.append(block)
        block_ensemble = self._add_metadata_to_settings(block_ensemble, created_blocks=created_blocks,
                                                        alternating=False, number_of_lasers=0)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)

        return created_blocks, created_ensembles, created_sequences

    def _create_generic_trigger(self, name='trigger', channels=[]):
        created_blocks = []
        created_ensembles = []
        created_sequences = []

        trig_element =  self._get_trigger_element(length=50e-9, increment=0., channels=channels)
        block = PulseBlock(name=name)
        block.append(trig_element)

        self._extend_to_min_samples(block)

        # prepare return vals
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((block.name, 0))
        created_blocks.append(block)
        block_ensemble = self._add_metadata_to_settings(block_ensemble, created_blocks=created_blocks,
                                                        alternating=False, number_of_lasers=0)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)

        return created_blocks, created_ensembles, created_sequences


    def _rad_to_deg(self, angle_rad):
        return angle_rad/(2*np.pi)*360

    def _deg_to_rad(self, angle_deg):
        return angle_deg/360 * 2*np.pi

    def _create_single_ppol(self, name='ppol', tau=0.5e-6, order=1, direction='up',
                            env_type=EnvelopeMethods.rectangle, order_P=1,
                            add_gate_ch='d_ch4', alternating=True):
            """
            based on polarisation_methods (s3 Pol20_polarize)
            """

            created_blocks = list()
            created_ensembles = list()
            created_sequences = list()
            rabi_period = self.rabi_period
            microwave_amplitude = self.microwave_amplitude
            microwave_frequency = self.microwave_frequency

            if tau / 4.0 - rabi_period / 2.0 < 0.0:
                self.log.error('PPol generation failed! Rabi period of {0:.3e} s is too long for start tau '
                               'of {1:.3e} s.'.format(rabi_period, tau))
                return

            # get readout element
            readout_element = self._get_readout_element()
            if add_gate_ch == '':
                readout_element[0].digital_high['d_ch4'] = False

            pihalfx_element = self.gen_nvision._get_mw_element_shaped(length=rabi_period / 4, increment=0.0,
                                                                      amp=microwave_amplitude, freq=microwave_frequency,
                                                                      phase=0,
                                                                      env_type=env_type, order_P=order_P)
            pihalfminusx_element = self.gen_nvision._get_mw_element_shaped(length=rabi_period / 4, increment=0.0,
                                                                           amp=microwave_amplitude,
                                                                           freq=microwave_frequency,
                                                                           phase=180.0,
                                                                           env_type=env_type, order_P=order_P
                                                                           )
            pihalfy_element = self.gen_nvision._get_mw_element_shaped(length=rabi_period / 4,
                                                                      increment=0.0,
                                                                      amp=microwave_amplitude,
                                                                      freq=microwave_frequency,
                                                                      phase=90.0,
                                                                      env_type=env_type, order_P=order_P)
            pihalfminusy_element = self.gen_nvision._get_mw_element_shaped(length=rabi_period / 4,
                                                                           increment=0.0,
                                                                           amp=microwave_amplitude,
                                                                           freq=microwave_frequency,
                                                                           phase=270.0,
                                                                           env_type=env_type, order_P=order_P)
            pix_element = self.gen_nvision._get_mw_element_shaped(length=rabi_period / 2,
                                                                  increment=0.0,
                                                                  amp=microwave_amplitude,
                                                                  freq=microwave_frequency,
                                                                  phase=0.0,
                                                                  env_type=env_type, order_P=order_P)
            piy_element = self.gen_nvision._get_mw_element_shaped(length=rabi_period / 2,
                                                                  increment=0.0,
                                                                  amp=microwave_amplitude,
                                                                  freq=microwave_frequency,
                                                                  phase=90.0,
                                                                  env_type=env_type, order_P=order_P)
            # get tau/4 element
            tau_element = self._get_idle_element(length=tau / 4.0 - rabi_period / 2, increment=0)

            block = PulseBlock(name=name)
            # actual (Pol 2.0)_2N sequence
            if direction == 'up':
                for n in range(2 * order):
                    block.append(pihalfminusx_element)
                    block.append(tau_element)
                    block.append(piy_element)
                    block.append(tau_element)
                    block.append(pihalfminusx_element)

                    block.append(pihalfy_element)
                    block.append(tau_element)
                    block.append(pix_element)
                    block.append(tau_element)
                    block.append(pihalfy_element)
                block.extend(readout_element)

                if alternating:
                    # alternates readout, not pol direction
                    for n in range(2 * order):
                        block.append(pihalfminusx_element)
                        block.append(tau_element)
                        block.append(piy_element)
                        block.append(tau_element)
                        block.append(pihalfminusx_element)

                        block.append(pihalfy_element)
                        block.append(tau_element)
                        block.append(pix_element)
                        block.append(tau_element)
                        block.append(pihalfy_element)

                    block[-1] = pihalfminusy_element
                    block.extend(readout_element)


            if direction == 'down':
                for n in range(2 * order):
                    block.append(pihalfy_element)
                    block.append(tau_element)
                    block.append(pix_element)
                    block.append(tau_element)
                    block.append(pihalfy_element)

                    block.append(pihalfminusx_element)
                    block.append(tau_element)
                    block.append(piy_element)
                    block.append(tau_element)
                    block.append(pihalfminusx_element)
                block.extend(readout_element)

                if alternating:
                    for n in range(2 * order):
                        block.append(pihalfy_element)
                        block.append(tau_element)
                        block.append(pix_element)
                        block.append(tau_element)
                        block.append(pihalfy_element)

                        block.append(pihalfminusx_element)
                        block.append(tau_element)
                        block.append(piy_element)
                        block.append(tau_element)
                        block.append(pihalfminusx_element)

                    block[-1] = pihalfx_element
                    block.extend(readout_element)


            created_blocks.append(block)
            # Create block ensemble
            block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
            block_ensemble.append((block.name, 0))

            # Create and append sync trigger block if needed
            # NO SYNC TRIGGER
            #created_blocks, block_ensemble = self._add_trigger(created_blocks, block_ensemble)
            # add metadata to invoke settings
            block_ensemble = self._add_metadata_to_settings(block_ensemble, created_blocks=created_blocks,
                                                            alternating=alternating, units=('s', ''),
                                                            labels=('tau', 'Signal'),
                                                            controlled_variable=[tau])
            # append ensemble to created ensembles
            created_ensembles.append(block_ensemble)
            return created_blocks, created_ensembles, created_sequences

    def _create_single_ramsey(self, name='ramsey', tau=500e-9, mw_phase=0.0,
                              laser_length=1500e-9, wait_length=1000e-9, ni_gate_length=-1e-9,
                              phase_readout_rad=0):

        use_ni_counter = False
        if ni_gate_length > 0.:
            use_ni_counter = True
            if self.gate_channel:
                self.logger.warning("Gated mode sensible with fastcounter, but found nicard counting enabled.")

        created_blocks = []
        created_ensembles = []
        created_sequences = []

        # prevent granularity problems
        rabi_period = self._adjust_to_samplingrate(self.rabi_period, 8)  # s
        tau = self._adjust_to_samplingrate(tau, 4)

        pi2_element = self._get_mw_element(length=rabi_period / 4,
                                              increment=0.0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0.0)
        pi2_element_read = self._get_mw_element(length=rabi_period / 4,
                                           increment=0.0,
                                           amp=self.microwave_amplitude,
                                           freq=self.microwave_frequency,
                                           phase=self._rad_to_deg(phase_readout_rad))
        tau_element = self._get_idle_element(length=tau, increment=0.0)

        # laser readout after MW
        aom_delay = self.laser_delay

        # note: fastcomtec triggers only on falling edge
        laser_gate_element = self._get_laser_gate_element(length=aom_delay - 20e-9, increment=0)
        laser_element = self._get_laser_element(length=laser_length - aom_delay + 20e-9, increment=0)
        delay_element = self._get_idle_element(length=aom_delay, increment=0)
        waiting_element = self._get_idle_element(length=wait_length, increment=0.0)

        # only a single tau, so we can operate sync_channel just like in gating mode
        if self.sync_channel:
            laser_gate_channels = [self.sync_channel, self.laser_channel]
            laser_sync_element = self._get_trigger_element(length=aom_delay - 20e-9, increment=0, channels=laser_gate_channels)

        block = PulseBlock(name=name)
        block.append(pi2_element)
        block.append(tau_element)
        block.append(pi2_element_read)
        if not use_ni_counter:  # normal, fastcounter acquisition
            if self.gate_channel:
                block.append(laser_gate_element)
            if self.sync_channel:
                block.append(laser_sync_element)

            block.append(laser_element)
        else:   # use nicard counter and gate away dark counts
            laser_element_1 = self._get_laser_element(length=aom_delay - 10e-9, increment=0)
            laser_gate_channels = [self.sync_channel, self.laser_channel]
            laser_gate_element = self._get_trigger_element(length=ni_gate_length + 20e-9, increment=0, channels=laser_gate_channels)
            gate_after_length = ni_gate_length + aom_delay - laser_length

            # makes sure that whole laser pulse is in ni gate
            # NOT wanted
            #if aom_delay > gate_after_length:
            #    gate_after_length = aom_delay
            gate_element_after_laser = self._get_trigger_element(length=gate_after_length, increment=0, channels=[self.sync_channel])
            # negative length values allowed: cut back laser_gate_element
            laser_element_2 = self._get_laser_element(length=laser_length - ni_gate_length - aom_delay - 10e-9, increment=0)

            if self.sync_channel:
                block.append(laser_element_1)
                block.append(laser_gate_element)
                block.append(laser_element_2) # may cut back laser_gate, st laser length correct
                if ni_gate_length + aom_delay >= laser_length:
                    block.append(gate_element_after_laser)


        block.append(delay_element)
        block.append(waiting_element)


        self._extend_to_min_samples(block, prepend=True)

        # prepare return vals
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((block.name, 0))
        created_blocks.append(block)
        block_ensemble = self._add_metadata_to_settings(block_ensemble, created_blocks=created_blocks,
                                                        alternating=False, number_of_lasers=1)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)

        return created_blocks, created_ensembles, created_sequences

    def _create_single_xy8(self, name='xy8', tau=500e-9, xy8_order=1,
                              laser_length=1500e-9, wait_length=1000e-9, ni_gate_length=-1e-9,
                              phase_readout_rad=0):

        use_ni_counter = False
        if ni_gate_length > 0.:
            use_ni_counter = True
            if self.gate_channel:
                self.logger.warning("Gated mode sensible with fastcounter, but found nicard counting enabled.")

        created_blocks = []
        created_ensembles = []
        created_sequences = []

        # prevent granularity problems
        rabi_period = self._adjust_to_samplingrate(self.rabi_period, 8)  # s
        real_tau = max(0, tau - self.rabi_period / 2)

        tau = self._adjust_to_samplingrate(real_tau, 4)


        # create the elements
        pihalf_element = self._get_mw_element(length=rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        pihalf_read = self._get_mw_element(length=rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=self._rad_to_deg(phase_readout_rad))

        pix_element = self._get_mw_element(length=rabi_period / 2,
                                           increment=0,
                                           amp=self.microwave_amplitude,
                                           freq=self.microwave_frequency,
                                           phase=0)
        piy_element = self._get_mw_element(length=rabi_period / 2,
                                           increment=0,
                                           amp=self.microwave_amplitude,
                                           freq=self.microwave_frequency,
                                           phase=90)
        tauhalf_element = self._get_idle_element(length=tau / 2, increment=0)
        tau_element = self._get_idle_element(length=tau, increment=0)

        # laser readout after MW
        aom_delay = self.laser_delay

        # note: fastcomtec triggers only on falling edge
        laser_gate_element = self._get_laser_gate_element(length=aom_delay - 20e-9, increment=0)
        laser_element = self._get_laser_element(length=laser_length - aom_delay + 20e-9, increment=0)
        delay_element = self._get_idle_element(length=aom_delay, increment=0)
        waiting_element = self._get_idle_element(length=wait_length, increment=0.0)

        # only a single tau, so we can operate sync_channel just like in gating mode
        if self.sync_channel:
            laser_gate_channels = [self.sync_channel, self.laser_channel]
            laser_sync_element = self._get_trigger_element(length=aom_delay - 20e-9, increment=0, channels=laser_gate_channels)

        xy8_block = PulseBlock(name=name)
        xy8_block.append(pihalf_element)
        xy8_block.append(tauhalf_element)
        for n in range(xy8_order):
            xy8_block.append(pix_element)
            xy8_block.append(tau_element)
            xy8_block.append(piy_element)
            xy8_block.append(tau_element)
            xy8_block.append(pix_element)
            xy8_block.append(tau_element)
            xy8_block.append(piy_element)
            xy8_block.append(tau_element)
            xy8_block.append(piy_element)
            xy8_block.append(tau_element)
            xy8_block.append(pix_element)
            xy8_block.append(tau_element)
            xy8_block.append(piy_element)
            xy8_block.append(tau_element)
            xy8_block.append(pix_element)
            if n != xy8_order - 1:
                xy8_block.append(tau_element)
        xy8_block.append(tauhalf_element)
        xy8_block.append(pihalf_read)

        if not use_ni_counter:  # normal, fastcounter acquisition
            if self.gate_channel:
                xy8_block.append(laser_gate_element)
            if self.sync_channel:
                xy8_block.append(laser_sync_element)
            xy8_block.append(laser_element)
        else:   # use nicard counter and gate away dark counts
            laser_element_1 = self._get_laser_element(length=aom_delay - 10e-9, increment=0)
            laser_gate_channels = [self.sync_channel, self.laser_channel]
            laser_gate_element = self._get_trigger_element(length=ni_gate_length + 20e-9, increment=0, channels=laser_gate_channels)
            gate_after_length = ni_gate_length + aom_delay - laser_length

            # makes sure that whole laser pulse is in ni gate
            # NOT wanted
            #if aom_delay > gate_after_length:
            #    gate_after_length = aom_delay
            gate_element_after_laser = self._get_trigger_element(length=gate_after_length, increment=0, channels=[self.sync_channel])
            # negative length values allowed: cut back laser_gate_element
            laser_element_2 = self._get_laser_element(length=laser_length - ni_gate_length - aom_delay - 10e-9, increment=0)

            if self.sync_channel:
                xy8_block.append(laser_element_1)
                xy8_block.append(laser_gate_element)
                xy8_block.append(laser_element_2) # may cut back laser_gate, st laser length correct
                if ni_gate_length + aom_delay >= laser_length:
                    xy8_block.append(gate_element_after_laser)

        xy8_block.append(delay_element)
        xy8_block.append(waiting_element)

        self._extend_to_min_samples(xy8_block, prepend=True)

        # prepare return vals
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((xy8_block.name, 0))
        created_blocks.append(xy8_block)

        block_ensemble = self._add_metadata_to_settings(block_ensemble, created_blocks=created_blocks,
                                                        alternating=False, number_of_lasers=1)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)

        return created_blocks, created_ensembles, created_sequences

    def _create_single_hahn(self, name='hahn', tau=500e-9, mw_phase=0.0,
                              laser_length=1500e-9, wait_length=1000e-9, ni_gate_length=-1e-9):

        use_ni_counter = False
        if ni_gate_length > 0.:
            use_ni_counter = True
            if self.gate_channel:
                self.logger.warning("Gated mode sensible with fastcounter, but found nicard counting enabled.")

        created_blocks = []
        created_ensembles = []
        created_sequences = []

        # prevent granularity problems
        rabi_period = self._adjust_to_samplingrate(self.rabi_period, 8)  # s
        tau = self._adjust_to_samplingrate(tau, 4)

        pi2_element = self._get_mw_element(length=rabi_period / 4,
                                              increment=0.0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0.0)
        pi_element = self._get_mw_element(length=rabi_period / 2,
                                           increment=0.0,
                                           amp=self.microwave_amplitude,
                                           freq=self.microwave_frequency,
                                           phase=0.0)
        tau_element = self._get_idle_element(length=tau, increment=0.0)

        # laser readout after MW
        aom_delay = self.laser_delay

        # note: fastcomtec triggers only on falling edge
        laser_gate_element = self._get_laser_gate_element(length=aom_delay - 20e-9, increment=0)
        laser_element = self._get_laser_element(length=laser_length - aom_delay + 20e-9, increment=0)
        delay_element = self._get_idle_element(length=aom_delay, increment=0)
        waiting_element = self._get_idle_element(length=wait_length, increment=0.0)

        # only a single tau, so we can operate sync_channel just like in gating mode
        if self.sync_channel:
            laser_gate_channels = [self.sync_channel, self.laser_channel]
            laser_sync_element = self._get_trigger_element(length=aom_delay - 20e-9, increment=0, channels=laser_gate_channels)

        block = PulseBlock(name=name)
        block.append(pi2_element)
        block.append(tau_element)
        block.append(pi_element)
        block.append(tau_element)
        block.append(pi2_element)

        if not use_ni_counter:  # normal, fastcounter acquisition
            if self.gate_channel:
                block.append(laser_gate_element)
            if self.sync_channel:
                block.append(laser_sync_element)

            block.append(laser_element)
        else:   # use nicard counter and gate away dark counts
            laser_element_1 = self._get_laser_element(length=aom_delay - 10e-9, increment=0)
            laser_gate_channels = [self.sync_channel, self.laser_channel]
            laser_gate_element = self._get_trigger_element(length=ni_gate_length + 20e-9, increment=0, channels=laser_gate_channels)
            gate_after_length = ni_gate_length + aom_delay - laser_length

            # makes sure that whole laser pulse is in ni gate
            # NOT wanted
            #if aom_delay > gate_after_length:
            #    gate_after_length = aom_delay
            gate_element_after_laser = self._get_trigger_element(length=gate_after_length, increment=0, channels=[self.sync_channel])
            # negative length values allowed: cut back laser_gate_element
            laser_element_2 = self._get_laser_element(length=laser_length - ni_gate_length - aom_delay - 10e-9, increment=0)

            if self.sync_channel:
                block.append(laser_element_1)
                block.append(laser_gate_element)
                block.append(laser_element_2) # may cut back laser_gate, st laser length correct
                if ni_gate_length + aom_delay >= laser_length:
                    block.append(gate_element_after_laser)


        block.append(delay_element)
        block.append(waiting_element)

        self._extend_to_min_samples(block, prepend=True)

        # prepare return vals
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((block.name, 0))
        created_blocks.append(block)
        block_ensemble = self._add_metadata_to_settings(block_ensemble, created_blocks=created_blocks,
                                                        alternating=False, number_of_lasers=1)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)

        return created_blocks, created_ensembles, created_sequences

    def _create_single_dd_mollow(self, name='dd_mollow_tau', tau=0.5e-6,
                               dd_type=DDMethods.CPMG, dd_order=1, ampl_mol=0.1, f_mol=1e6, phase_mod='',
                               env_type=EnvelopeMethods.rectangle, order_P=1,
                               alternating=True, shaped_weak_drive=True,
                               ):
        """

        """
        # based on dd_iqo_sequences:: generate_dd_mollow_tau
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        tau_pspacing = self.tau_2_pulse_spacing(tau)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self.gen_nvision._get_mw_element_shaped(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0,
                                              env_type=env_type, order_P=order_P)

        # define a function to create phase shifted pi pulse elements
        def pi_element_function(xphase):
            return self.gen_nvision._get_mw_element_shaped(length=self.rabi_period / 2,
                                        increment=0,
                                        amp=self.microwave_amplitude,
                                        freq=self.microwave_frequency,
                                        phase=xphase,
                                        env_type=env_type, order_P=order_P)

        def get_mollow_phase(phase_idx, phases=None):
            phi = 0
            if not phases:
                phi = 0
            else:
                # ensure correct phase after last pi pulse
                if phase_idx == len(phases):
                    phi = phases[0]
                else:
                    phi = phases[phase_idx]
            return phi

        def tau2_mollow_element_function(phase_idx, phases=None, shaped=False):
            """
            Alternate the phases of the signal/waiting element according to an idx and a phases array.
            :param phase_idx:
            :param phases:
            :return:
            """
            phi = get_mollow_phase(phase_idx, phases)
            if shaped:
                element = self.gen_nvision._get_mw_element_shaped(length=tau_pspacing / 2, increment=0,
                                               amp=ampl_mol, freq=self.microwave_frequency + f_mol,
                                               phase=phi,
                                               env_type=env_type, order_P=order_P)
            else:
                element = self.gen_nvision._get_mw_element_shaped(length=tau_pspacing / 2, increment=0,
                                                                  amp=ampl_mol, freq=self.microwave_frequency + f_mol,
                                                                  phase=phi,
                                                                  env_type=EnvelopeMethods.rectangle, order_P=order_P)

            return element

        # Use a 180 deg phase shifted pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self.gen_nvision._get_mw_element_shaped(length=self.rabi_period / 4,
                                                                      increment=0,
                                                                      amp=self.microwave_amplitude,
                                                                      freq=self.microwave_frequency,
                                                                      phase=180,
                                                                      env_type=env_type, order_P=order_P)
        else:
            pi3half_element = self.gen_nvision._get_mw_element_shaped(length=3 * self.rabi_period / 4,
                                                                      increment=0,
                                                                      amp=self.microwave_amplitude,
                                                                      freq=self.microwave_frequency,
                                                                      phase=0,
                                                                      env_type=env_type, order_P=order_P)

        phase_mod = csv_2_list(phase_mod)
        all_phases = [[get_mollow_phase(idx_pi, phase_mod), get_mollow_phase(idx_pi + 1, phase_mod)]
                      for idx_pi in range(dd_type.suborder)]
        self.log.debug(f"Phase modulation in {dd_type}: {all_phases}")
        # tauhalf_element = self._get_idle_element(length=start_tau_pspacing / 2, increment=tau_step / 2)
        # tau_element = self._get_idle_element(length=start_tau_pspacing, increment=tau_step)

        # Create block and append to created_blocks list
        dd_block = PulseBlock(name=name)
        dd_block.append(pihalf_element)
        for n in range(dd_order):
            # create the DD sequence for a single order
            for pulse_number in range(dd_type.suborder):
                dd_block.append(tau2_mollow_element_function(pulse_number, phase_mod, shaped=shaped_weak_drive))
                dd_block.append(pi_element_function(dd_type.phases[pulse_number]))
                dd_block.append(tau2_mollow_element_function(pulse_number + 1, phase_mod, shaped=shaped_weak_drive))
        dd_block.append(pihalf_element)
        dd_block.append(laser_element)
        dd_block.append(delay_element)
        dd_block.append(waiting_element)
        if alternating:
            dd_block.append(pihalf_element)
            for n in range(dd_order):
                # create the DD sequence for a single order
                for pulse_number in range(dd_type.suborder):
                    dd_block.append(tau2_mollow_element_function(pulse_number, phase_mod, shaped=shaped_weak_drive))
                    dd_block.append(pi_element_function(dd_type.phases[pulse_number]))
                    dd_block.append(tau2_mollow_element_function(pulse_number + 1, phase_mod, shaped=shaped_weak_drive))
            dd_block.append(pi3half_element)
            dd_block.append(laser_element)
            dd_block.append(delay_element)
            dd_block.append(waiting_element)
        created_blocks.append(dd_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((dd_block.name, 1 - 1))

        # Create and append sync trigger block if needed
        # self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        number_of_lasers = 1 * 2 if alternating else 1
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = [tau]
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def _create_single_ise(self, name='ise', t_ise=1e-6, f_res='', df_mw_sweep=10e6,
                                    mw_sweep_speed=3e12, amp_mw_sweep=0.25,
                                    both_sweep_polarities=False):

        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # create the laser element
        """
        laser_element = self._get_laser_element(length=t_laser, increment=0)

        # create the laser element with "jump" signal
        laser_element_jump = self._get_laser_element(length=t_laser, increment=0)
        laser_element_jump.digital_high[jump_channel] = True
        """

        t_mw_ramp = df_mw_sweep / mw_sweep_speed

        # create n mw chirps
        n_mw_chirps = int(np.ceil(t_ise/t_mw_ramp))
        if t_ise % t_mw_ramp != 0.:
            t_ise = n_mw_chirps * t_mw_ramp
            self.log.info(f"Adjusting t_ise to {t_ise*1e6:.3f} us to fit in {n_mw_chirps}"
                          f" t_mw= {t_mw_ramp*1e6:.3f} us. Sweep speed= {mw_sweep_speed/1e12} MHz/us")

        if not f_res:
            mw_freq_center = self.microwave_frequency
        else:
            mw_freq_center = float(f_res)

        freq_range = df_mw_sweep
        mw_freq_start = mw_freq_center - freq_range / 2.
        mw_freq_end = mw_freq_center + freq_range / 2

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        mw_sweep_element = self._get_mw_element_linearchirp(length=t_mw_ramp,
                                                          increment=0,
                                                          amplitude=amp_mw_sweep,
                                                          start_freq=mw_freq_start,
                                                          stop_freq=mw_freq_end,
                                                          phase=0)

        mw_sweep_depol_element = self._get_mw_element_linearchirp(length=t_mw_ramp,
                                                                 increment=0,
                                                                 amplitude=amp_mw_sweep,
                                                                 start_freq=mw_freq_end,
                                                                 stop_freq=mw_freq_start,
                                                                 phase=0)



        # Create block and append to created_blocks list
        ise_block = PulseBlock(name=name)

        for i in range(n_mw_chirps):
            ise_block.append(mw_sweep_element)
            if both_sweep_polarities:
                ise_block.append(mw_sweep_depol_element)

        ise_block.append(laser_element)
        ise_block.append(delay_element)
        ise_block.append(waiting_element)

        # Create block ensemble and append to created_ensembles list
        created_blocks.append(ise_block)
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((ise_block.name, 0))


        # Create and append sync trigger block if needed
        # no trigger as this sequence is used by other sequences that add sync trigger
        #self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        number_of_lasers = 1
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = [0]
        block_ensemble.measurement_information['units'] = ('a.u.', '')
        block_ensemble.measurement_information['labels'] = ('data point', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences


    def _extend_to_min_samples(self, pulse_block, prepend=True):

        min_samples = self.pulse_generator_constraints.waveform_length.min

        if self.get_pulseblock_duration(pulse_block) * self.pulse_generator_settings['sample_rate'] < min_samples:
            length_idle = min_samples / self.pulse_generator_settings['sample_rate'] - self.get_pulseblock_duration(pulse_block)
            idle_element_extra = self._get_idle_element(length=length_idle, increment=0.0)

            if prepend:
                pulse_block.insert(0, idle_element_extra)
            else:
                pulse_block.append(idle_element_extra)

    def get_pulseblock_duration(self, pulse_block):
        # keep here, not general enough to merge into pulse_objects.py
        if pulse_block.increment_s != 0:
            self.log.error("Can't determine length of a PulseBlockElement with increment!")
            return -1

        return pulse_block.init_length_s
