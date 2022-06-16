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


class ModeSpectrumLogic(GenericLogic):
    # declare connectors
    oscilloscope = Connector(interface='OscilloscopeInterface')
    savelogic = Connector(interface='SaveLogic')
    fitlogic = Connector(interface='FitLogic')

    # config options
    fc = StatusVar('fits', None)
    cavity_length = StatusVar('cavity_length', 480) # µm
    ROCa = StatusVar('ROCa', 270) # µm
    ROCb = StatusVar('ROCb', 360) # µm
    time_base = StatusVar('time_base', 5e-3)
    current_channel = StatusVar('current_channel', 1)
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

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        pass

    ########################################################################
    #                       Hardware control                               #
    ########################################################################
    def get_single_trace(self, channel=1):
        self.time_axis = self._oscilloscope.get_xaxis()
        trace = self._oscilloscope.RunSingle(channel)
        self._current_trace = np.array(trace)
        self.sigUpdateGui.emit()
    
    ####################################################################
    #                       calculations                               #
    ####################################################################
    def vSpec(self, n, m, L, R1, R2):
        return 1/(2*np.pi)*((m+1/2)*np.arccos(-(1-L/(R1*np.cos(np.pi/6)))) + (n+1/2)*np.arccos(-(1-L*np.cos(np.pi/6)/(R2))) + np.pi/2*(1-(-1)**m))

    def vSpecFSR(self, n, m, L, R1, R2):
        return self.vSpec(n, m, L, R1, R2) - self.vSpec(0, 0, L, R1, R2)

    def xModes(self, L, R1, R2):
        return [self.vSpecFSR(0,0,L,R1,R2),self.vSpecFSR(1,0,L,R1,R2),self.vSpecFSR(0,1,L,R1,R2),
                self.vSpecFSR(1,1,L,R1,R2),self.vSpecFSR(2,0,L,R1,R2),self.vSpecFSR(0,2,L,R1,R2),
                self.vSpecFSR(3,0,L,R1,R2),self.vSpecFSR(0,3,L,R1,R2)]

    def calc_Spectrum(self, length, ROCa, ROCb):
        self.cavity_length = length
        self.ROCa = ROCa
        self.ROCb = ROCb
        self.spectrum_x = self.xModes(self.cavity_length, self.ROCa, self.ROCb)
        self.spectrum_y = [1,0.4,0.4,0.2,0.1,0.1,0.05,0.05]

    def do_fit(self, fit_function=None, x_data=None, y_data=None):
        """
        Execute the currently configured fit on the measurement data. Optionally on passed data
        """
        if (x_data is None) or (y_data is None):
            y_data = self._current_trace
        if fit_function is not None and isinstance(fit_function, str):
            if fit_function in self.get_fit_functions():
                    self.fc.set_current_fit(fit_function)

                    self.spectrum_fit_x, self.spectrum_fit_y, result = self.fc.do_fit(self.time_axis, y_data)
                    if result is None:
                        self.result_str_dict = {}
                    else:
                        self.result_str_dict = result.result_str_dict
                    scale = 1/(self.result_str_dict['Position 1']['value'] - self.result_str_dict['Position 0']['value'])
                    self.spectrum_fit_x = (self.spectrum_fit_x - self.result_str_dict['Position 0']['value']) * scale
                    self.time_axis = (self.time_axis-self.result_str_dict['Position 0']['value']) * scale
                    self.sig_fit_updated.emit()
        else:
            self.fc.set_current_fit('No Fit')
            if fit_function != 'No Fit':
                self.log.warning('Fit function "{0}" not available in Finesse fit container.'
                                    ''.format(fit_function))
        return 0

    @fc.constructor
    def sv_set_fits(self, val):
        # Setup fit container
        fc = self.fitlogic().make_fit_container('cavity spectrum', '1d')
        fc.set_units(['s', 'V'])
        if isinstance(val, dict) and len(val) > 0:
            fc.load_from_dict(val)
        else:
            d1 = OrderedDict()
            d1['Two Lorentzian peaks'] = {
                'fit_function': 'lorentziandouble',
                'estimator': 'peak'
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
            filelabel = 'cavity_spec_' + tag
        else:
            filelabel = 'cavity_spec'

        data = OrderedDict()
        data['measurement time (s)'] = self.time_axis
        data['photodiode signal (V)'] = self._current_trace
        
        parameters = OrderedDict()
        parameters['cavity length (um)'] = self.cavity_length
        parameters['ROCa (um)'] = self.ROCa
        parameters['ROCb (um)'] = self.ROCb

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
            filelabel = 'cavity_spec_' + tag
        else:
            filelabel = 'cavity_spec'

        data = OrderedDict()
        data['measurement time (s)'] = self.time_axis
        data['photodiode signal (V)'] = self._current_trace
        
        parameters = OrderedDict()
        parameters['cavity length (um)'] = self.cavity_length
        parameters['ROCa (um)'] = self.ROCa
        parameters['ROCb (um)'] = self.ROCb
        
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
          