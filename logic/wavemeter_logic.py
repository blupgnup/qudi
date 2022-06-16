# -*- coding: utf-8 -*-

"""
This file contains the logic responsible for coordinating laser scanning.

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
import time
import datetime

from core.connector import Connector
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex


class WavemeterLogic(GenericLogic):
    sig_data_updated = QtCore.Signal(float, float)

    # declare connectors
    wavemeter1 = Connector(interface='WavemeterInterface')

    # config opts
    _logic_acquisition_timing = ConfigOption('logic_acquisition_timing', 100.0, missing='warn')

    def __init__(self, config, **kwargs):
        """ Create WavemeterLoggerLogic object with connectors.

          @param dict config: module configuration
          @param dict kwargs: optional parameters
        """
        super().__init__(config=config, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()
        
        self.current_wavelength = 1

        self.enabled = False
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(self._logic_acquisition_timing)
        self.timer.timeout.connect(self.loop)

        self.hardware_thread = QtCore.QThread()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._wavemeter_device = self.wavemeter1()

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        pass

    def start_acquisition(self, mode='vacuum'):
        """ Start the data recording loop.
        """
        self._wavemeter_device.start_acqusition()
        self.enabled = True
        self.acquisitionmode = mode
        self.timer.start(self._logic_acquisition_timing)

    def stop_acquisition(self):
        """ Stop the data recording loop.
        """
        self.enabled = False
        self._wavemeter_device.stop_acqusition()

    def loop(self, mode='vac'):
        """ Execute step in the data recording loop: save one of each control and process values
        """
        wavelength = self._wavemeter_device.get_current_wavelength(self.acquisitionmode)
        frequency = self._wavemeter_device.get_current_frequency()
        self.sig_data_updated.emit(wavelength, frequency)
        if self.enabled:
            self.timer.start(self._logic_acquisition_timing)
