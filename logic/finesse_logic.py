# -*- coding: utf-8 -*-
"""
This file contains the Qudi logic class that captures and processes fluorescence spectra.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import datetime
import time

from qtpy import QtCore
from collections import OrderedDict
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from core.connector import Connector
from core.configoption import ConfigOption
from core.statusvariable import StatusVar
from core.util.mutex import Mutex
from core.util.network import netobtain
from logic.generic_logic import GenericLogic


class FinesseLogic(GenericLogic):
    # declare connectors
    oscilloscope = Connector(interface='OscilloscopeInterface')
    savelogic = Connector(interface='SaveLogic')
    fitlogic = Connector(interface='FitLogic')

    # config options
    _logic_acquisition_timing = ConfigOption('logic_acquisition_timing', 20.0, missing='warn')
    fc = StatusVar('fits', None)
    cavity_length = StatusVar('cavity_length', 460) # µm
    cavity_error = StatusVar('cavity_error', 0.02) # µm
    refresh_timing = StatusVar('refresh_timing', 200)
    eom_frequency = StatusVar('eom_frequency', 1004) # MHz
    time_base = StatusVar('time_base', 5e-3)
    current_channel = StatusVar('current_channel', 1)
    vertical_scale = StatusVar('vertical_scale', 20e-3)
    record_length = StatusVar('record_length', 10000)
    dirname = StatusVar('directory name', 'none')

    # signals
    sigUpdateGui = QtCore.Signal()
    sig_handle_timer = QtCore.Signal(bool, int)
    sig_fit_updated = QtCore.Signal()
    sig_Parameter_Updated = QtCore.Signal(dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # locking for thread safety
        self.threadlock = Mutex()
        self._current_trace = []

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        # Sets connections between signals and functions
        self._oscilloscope = self.oscilloscope()
        self._save_logic = self.savelogic()
        self._fit_logic = self.fitlogic()

        self.stopRequested = False
        #self.scope_stetting(self.time_base, self.record_length, self.vertical_scale)

        self.enabled = False
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(self.refresh_timing/1000)
        self.timer.timeout.connect(self.acq_loop)

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        if self.module_state() == 'locked':
            self.stop_odmr_scan()
        timeout = 30.0
        start_time = time.time()
        while self.module_state() == 'locked':
            time.sleep(0.5)
            timeout -= (time.time() - start_time)
            if timeout <= 0.0:
                self.log.error('Failed to properly deactivate odmr logic. Odmr scan is still '
                               'running but can not be stopped after 30 sec.')
                break

        self._oscilloscope.RunSTOP()

    ########################################################################
    #                       Hardware control                               #
    ########################################################################
    def handle_trace(self, trace):
        self._current_trace = np.array(trace)
        self.sigUpdateGui.emit()

    def get_single_trace(self, channel=1):
        self.time_axis = self._oscilloscope.get_xaxis()
        trace = self._oscilloscope.RunSingle(channel)
        self._current_trace = np.array(trace)
        self.sigUpdateGui.emit()
    
    def start_acquisition(self, channel=1, refreshrate=300.):
        self.current_channel = channel
        self.get_single_trace(channel)
        self.refresh_timing = refreshrate
        self._oscilloscope.RunContinous(channel)
        self.enabled = True
        self.timer.start(self.refresh_timing)

    def acq_loop(self):
        self.time_axis = self._oscilloscope.get_xaxis()
        trace = self._oscilloscope.getData_cont(self.current_channel)
        if len(trace)==0:
            self.time_axis = np.linspace(0, 1, self.record_length)
            trace = np.zeros(self.record_length)
        self.handle_trace(trace)
        if self.enabled:
            self.timer.start(self.refresh_timing)

    def stop_acquisition(self):
        #self._oscilloscope.RunSTOP()
        self.enabled = False
        return 0

    def scope_stetting(self, timebase=5e-3, recordlength=1000, scale=10e-3):
        self.time_base = timebase
        self._oscilloscope.SetTimeBase(self.time_base)
        self.record_length = recordlength
        self._oscilloscope.SetRecordLength(self.record_length)
        self.vertical_scale = scale
        self._oscilloscope.SetVerticalScale(self.current_channel, self.vertical_scale)

    ####################################################################
    #                       calculations                               #
    ####################################################################
    def calc_FSR(self, length, error):
        self.cavity_length = length
        update_dict = {'cavity_length': self.cavity_length}
        self.sig_Parameter_Updated.emit(update_dict)
        self.FSR = 299792458/(length*1e3)
        self.FSR_error = 299792458*error/(length**2*1e3)
        return self.FSR, self.FSR_error

    def do_fit(self, fit_function=None, x_data=None, y_data=None, chi=0.1):
        """
        Execute the currently configured fit on the measurement data. Optionally on passed data
        """
        if (x_data is None) or (y_data is None):
            y_data = self._current_trace

        if fit_function is not None and isinstance(fit_function, str):
            if fit_function in self.get_fit_functions():
                if fit_function in ['Lorentzian peak with sidebands']:
                    self.fc.set_current_fit(fit_function)
                    self.cavity_fit_x, self.cavity_fit_y, result = self.fc.do_fit(self.time_axis, y_data)
                    if result is None:
                        self.result_str_dict = {}
                    else:
                        self.result_str_dict = result.result_str_dict
                    if self.result_str_dict['chi_sqr']['value'] < chi:
                        (self.cavity_finesse, self.cavity_finesse_error) = self.finesse(fit_function)
                    else:
                        self.cavity_finesse = 0
                        self.cavity_finesse_error = 0
                    self.sig_fit_updated.emit()
                else:
                    self.fc.set_current_fit(fit_function)

                    self.cavity_fit_x, self.cavity_fit_y, result = self.fc.do_fit(self.time_axis, y_data)
                    if result is None:
                        self.result_str_dict = {}
                    else:
                        self.result_str_dict = result.result_str_dict

                    (self.cavity_finesse, self.cavity_finesse_error) = self.finesse(fit_function)
                    self.sig_fit_updated.emit()
            else:
                self.fc.set_current_fit('No Fit')
                if fit_function != 'No Fit':
                    self.log.warning('Fit function "{0}" not available in Finesse fit container.'
                                     ''.format(fit_function))
        return 0

    def finesse(self, fit_function):
        if fit_function is not None and isinstance(fit_function, str):
            if fit_function in ['Two Lorentzian peaks']:
                finesse = np.mean([self.result_str_dict['Splitting']['value']/self.result_str_dict['FWHM 0']['value'],
                                  self.result_str_dict['Splitting']['value']/self.result_str_dict['FWHM 1']['value']])
                error_finesse = np.std([self.result_str_dict['Splitting']['value']/self.result_str_dict['FWHM 0']['value'],
                                       self.result_str_dict['Splitting']['value']/self.result_str_dict['FWHM 1']['value']])
                return finesse, error_finesse
            elif fit_function in ['Lorentzian peak with sidebands']:
                Splitting = np.mean([self.result_str_dict['Splitting left']['value'], self.result_str_dict['Splitting right']['value']])
                self.conversion = self.eom_frequency/(Splitting)
                Linewidth = self.result_str_dict['FWHM 1']['value']*self.conversion
                finesse = self.FSR*1e3/Linewidth
                error_finesse = self.FSR/(self.result_str_dict['FWHM 1']['value']*self.eom_frequency)*np.std([self.result_str_dict['Splitting left']['value'], self.result_str_dict['Splitting right']['value']]) + self.FSR_error*1e3/Linewidth + self.FSR*1e3/(self.result_str_dict['FWHM 1']['value']**2*self.conversion)*self.result_str_dict['FWHM 1']['error']
                return finesse, error_finesse
            else:
                return 0, 0
        else:
            return 0, 0

    @fc.constructor
    def sv_set_fits(self, val):
        # Setup fit container
        fc = self.fitlogic().make_fit_container('cavity transmission', '1d')
        fc.set_units(['s', 'V'])
        if isinstance(val, dict) and len(val) > 0:
            fc.load_from_dict(val)
        else:
            d1 = OrderedDict()
            d1['Lorentzian peak'] = {
                'fit_function': 'lorentzian',
                'estimator': 'peak'
                }
            d1['Two Lorentzian peaks'] = {
                'fit_function': 'lorentziandouble',
                'estimator': 'peak'
                }
            d1['Three Lorentzian peaks'] = {
                'fit_function': 'lorentziantriple',
                'estimator': 'peak'
                }
            d1['Lorentzian peak with sidebands'] = {
                'fit_function': 'lorentziantriple',
                'estimator': 'sidebands'
                }
            default_fits = OrderedDict()
            default_fits['1d'] = d1
            fc.load_from_dict(default_fits)
        return fc

    @fc.representer
    def sv_get_fits(self, val):
        """ save configured fits """
        if len(val.fit_list) > 0:
            return val.save_to_dict()
        else:
            return None

    def get_fit_functions(self):
        """ Return the hardware constraints/limits
        @return list(str): list of fit function names
        """
        return list(self.fc.fit_list)

    def save_data(self, tag=None, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.now()
        if tag is not None and len(tag) > 0:
            filelabel = 'cavity_trans_' + tag
        else:
            filelabel = 'cavity_trans'

        data = OrderedDict()
        data['measurement time (s)'] = self.time_axis
        data['photodiode signal (V)'] = self._current_trace
        
        parameters = OrderedDict()
        parameters['modulation frequency (MHz)'] = self.eom_frequency
        parameters['cavity length (um)'] = self.cavity_length

        self._save_logic.save_data(data,
                                   filepath=self.dirname,
                                   filelabel=filelabel,
                                   filetype='p',
                                   parameters=parameters,
                                   fmt='%.6e',
                                   delimiter='\t',
                                   timestamp=timestamp)

    def save_fig(self, tag=None, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.now()
        if tag is not None and len(tag) > 0:
            filelabel = 'cavity_trans_' + tag
        else:
            filelabel = 'cavity_trans'

        data = OrderedDict()
        data['measurement time (s)'] = self.time_axis
        data['photodiode signal (V)'] = self._current_trace
        
        parameters = OrderedDict()
        parameters['modulation frequency (MHz)'] = self.eom_frequency
        parameters['cavity length (um)'] = self.cavity_length
        
        FontProp = fm.FontProperties(size=20)
        LabelFontProp = fm.FontProperties(size=20)

        freq_axis = (self.time_axis-self.result_str_dict['Position 1']['value'])*self.conversion

        fig = plt.figure(figsize=(8.7, 6))
        axes = fig.add_subplot(1, 1, 1)
        axes.xaxis.get_label().set_fontproperties(FontProp)
        axes.yaxis.get_label().set_fontproperties(FontProp)
        for label in (axes.get_xticklabels() + axes.get_yticklabels()):
            label.set_fontproperties(LabelFontProp)
        axes.tick_params(direction='in', length=5,
                        bottom=True, top=True, left=True, right=True, pad=10)
        axes.minorticks_on()
        axes.tick_params(direction='in', which='minor',
                        bottom=True, top=True, left=True, right=True)

        plt.locator_params(axis='y', nbins=4)

        axes.plot(freq_axis, self._current_trace*1e3, linewidth=1)
        axes.set_xlabel('frequency (MHz)', labelpad=15)
        axes.set_ylabel('photodiode signal (mV)')
        fig.tight_layout(rect=[0,-0.015,1,1.025])

        self._save_logic.save_data(data,
                            filepath=self.dirname,
                            filelabel=filelabel,
                            parameters=parameters,
                            fmt='%.6e',
                            filetype='p',
                            delimiter='\t',
                            timestamp=timestamp,
                            plotfig=fig)
          