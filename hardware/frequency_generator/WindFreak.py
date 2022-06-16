# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware interface for pulsing devices.

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

import visa
import time
from core.module import Base
from core.configoption import ConfigOption
from core.statusvariable import  StatusVar
from interface.frequencygenerator_interface import FrequencyGeneratorInterface
from core.util.mutex import Mutex

try:
    from windfreak import SynthHD
except ImportError:
    raise ImportError('WindFreak module not found. Please install from "pip install windfreak"')


class WindFreak(Base, FrequencyGeneratorInterface):
    _serial_device = ConfigOption('serial_device', 'COM3', missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.lock = Mutex()

    def on_activate(self):
        """ Establish connection to the WindFreak"""
        self.synth = SynthHD(self._serial_device)
        self.synth.init()

    def on_deactivate(self):
        self.generator_off(ch=0)
        self.generator_off(ch=1)
        pass

    def generator_on(self, ch=None):
        self.synth[ch].enable = True
        pass

    def generator_off(self, ch=None):
        self.synth[ch].enable = False
        pass

    def set_power_level(self, amplitude=None, ch=None):
        self.synth[ch].power = amplitude
        pass
    
    def get_power_level(self, ch=None):
        return self.synth[ch].power

    def set_frequency(self, freq=None, ch=None):
        self.synth[ch].frequency = freq

    def get_frequency(self, ch=None):
        return self.synth[ch].frequency

    def set_phase(self, phase=None, ch=None):
        self.synth[ch].phase = phase
    
    def get_phase(self, ch=None):
        return self.synth[ch].phase

    def get_temp(self, ch=None):
        return self.synth[ch].read('temperature')
    
    def get_active_channels(self):
        stat = []
        if self.synth[0].enable is True:
            stat.append(1)
        else:
            stat.append(0)
        if self.synth[1].enable is True:
            stat.append(1)
        else:
            stat.append(0)
        return stat