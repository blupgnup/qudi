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

from qtpy import QtCore
from collections import OrderedDict
import numpy as np
import matplotlib.pyplot as plt

import time

from core.connector import Connector
from core.configoption import ConfigOption
from core.statusvariable import StatusVar
from core.util.mutex import Mutex
from core.util.network import netobtain
from logic.generic_logic import GenericLogic


class FinesseCalcLogic(GenericLogic):
    # config options
    cavity_length = StatusVar('cavity_length', 520) # µm
    fiber_dia = StatusVar('fiber_dia', 90) # µm
    ROCa = StatusVar('ROCa', 270) # µm
    ROCb = StatusVar('ROCb', 360) # µm
    rms = StatusVar('rms', 0.22) # nm
    T1 = StatusVar('T1', 80)# ppm
    T2 = StatusVar('T2', 200) # ppm
    La = StatusVar('La', 4) # ppm
    wavelength = StatusVar('wavelength', 698) # nm
    Lc = 0
    Ls = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        # Sets connections between signals and functions
        pass

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        pass

    ####################################################################
    #                       calculations                               #
    ####################################################################
    def calc_beamradii(self, length, ROCa, ROCb):
        ROCeff = np.mean([ROCa/np.cos(30*2*np.pi/360),ROCb*np.cos(30*2*np.pi/360)])
        ROCeff_error = np.std([ROCa/np.cos(30*2*np.pi/360),ROCb*np.cos(30*2*np.pi/360)])
        mirror_beam_radii = np.sqrt(self.wavelength*1e-3*ROCeff/np.pi*
                                    np.sqrt(length/(2*ROCeff-length)))
        return mirror_beam_radii

    def calc_clipping(self, length, dia, ROCa, ROCb):
        beamradii = self.calc_beamradii(length, ROCa, ROCb)
        Lc = np.exp(-2*(dia/2)**2/beamradii**2)*1e6
        return Lc

    def calc_scattering_simple(self, rms):
        self.rms =rms
        self.Ls = (4*np.pi*rms*1e-6/(self.wavelength*1e-9))**2
        return 3*self.Ls

    def calc_scattering_simpleangle(self, rms):
        self.rms =rms
        self.Ls = (4*np.pi*rms*1e-6/(self.wavelength*1e-9)*np.cos(30*2*np.pi/360))**2
        return 3*self.Ls

    def calc_scattering_advanced(self, rms):
        self.rms =rms
        self.Ls = 64/3*(np.pi**4*(rms*1e-6*123*1e-9)**2)/(self.wavelength*1e-9)**4
        return 3*self.Ls

    def calc_finesse(self, T1, T2, La):
        Lc = self.calc_clipping(self.cavity_length, self.fiber_dia, self.ROCa, self.ROCb)
        finesse = 2*np.pi/(2*T1+T2+3*La+3*self.Ls+Lc)*1e6
        return finesse

    def plot_finesse_fiber(self, length, dia):
        Lc = self.calc_clipping(length, dia, self.ROCa, self.ROCb)
        finesse = 2*np.pi/(2*self.T1+self.T2+3*self.La
                           +3*self.Ls
                           +Lc)*1e6
        return finesse