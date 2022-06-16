#-*- coding: utf-8 -*-
"""
Laser management.

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

import time
import numpy as np
from qtpy import QtCore

from core.connector import Connector
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from core.statusvariable import StatusVar


class FrequencyGeneratorLogic(GenericLogic):
    """ Logic module agreggating multiple hardware switches.
    """
    ch1_freq = StatusVar('ch1_frequency', 53000000)
    ch2_freq = StatusVar('ch2_frequency', 53000000)
    ch1_pwr = StatusVar('ch1_power', -5)
    ch2_pwr = StatusVar('ch2_power', -5)
    ch1_phase = StatusVar('ch1_phase', 0)
    ch2_phase = StatusVar('ch2_phase', 0)

    # waiting time between queries im milliseconds
    generator = Connector(interface='FrequencyGeneratorInterface')

    queryInterval = ConfigOption('query_interval', 1000)
    sigUpdate = QtCore.Signal()

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self._generator = self.generator()

        self.set_frequency(0, self.ch1_freq)
        self.set_frequency(1, self.ch2_freq)
        self.set_power(0, self.ch1_pwr)
        self.set_power(1, self.ch2_pwr)
        self.set_phase(0, self.ch1_phase)
        self.set_phase(1, self.ch2_phase)

        self.stopRequest = False

        self.queryTimer = QtCore.QTimer()
        self.queryTimer.setInterval(self.queryInterval)
        self.queryTimer.setSingleShot(False)
        self.queryTimer.timeout.connect(self.check_temp_loop, QtCore.Qt.QueuedConnection)

        self.check_rf_state()
        self.start_query_loop()

    def on_deactivate(self):
        """ Deactivate modeule.
        """
        self.stop_query_loop()
        for i in range(5):
            time.sleep(self.queryInterval / 1000)
            QtCore.QCoreApplication.processEvents()

    @QtCore.Slot()
    def check_temp_loop(self):
        """ Get power, current, shutter state and temperatures from laser. """
        if self.stopRequest:
            if self.module_state.can('stop'):
                self.module_state.stop()
            self.stopRequest = False
            return
        qi = self.queryInterval
        try:
            #print('laserloop', QtCore.QThread.currentThreadId())
            self.tempch1 = self._generator.get_temp(0)
            self.tempch2 = self._generator.get_temp(1)
        except:
            qi = 3000
            self.log.exception("Exception in temp status loop, throttling refresh rate.")

        self.sigUpdate.emit()
        self.queryTimer.start(qi)

    @QtCore.Slot()
    def start_query_loop(self):
        """ Start the readout loop. """
        self.module_state.run()
        self.queryTimer.start(self.queryInterval)

    @QtCore.Slot()
    def stop_query_loop(self):
        """ Stop the readout loop. """
        self.stopRequest = True
        self.module_state.stop()
        self.queryTimer.stop()
        for i in range(10):
            if not self.stopRequest:
                return
            QtCore.QCoreApplication.processEvents()
            time.sleep(self.queryInterval/1000)


    @QtCore.Slot(bool)
    def check_rf_state(self):
        """ Turn laser on or off. """
        self._generator.get_active_channels()
        self.sigUpdate.emit()

    @QtCore.Slot(float)
    def set_frequency(self, ch, freq):
        self._generator.set_frequency(freq, ch)
        self.sigUpdate.emit()
        if ch is 0:
            self.ch1_freq = freq
        else:
            self.ch2_freq = freq

    @QtCore.Slot(float)
    def read_frequency(self, ch):
        return self._generator.get_frequency(ch)

    @QtCore.Slot(float)
    def set_power(self, ch, amplitude):
        self._generator.set_power_level(amplitude, ch)
        self.sigUpdate.emit()
        if ch is 0:
            self.ch1_pwr = amplitude
        else:
            self.ch2_pwr = amplitude

    @QtCore.Slot(float)
    def read_power(self, ch):
        return self._generator.get_power_level(ch)

    @QtCore.Slot(float)
    def set_phase(self, ch, phase):
        self._generator.set_phase(phase, ch)
        self.sigUpdate.emit()
        if ch is 0:
            self.ch1_phase = phase
        else:
            self.ch2_phase = phase

    @QtCore.Slot(float)
    def read_phase(self, ch):
        return self._generator.get_phase(ch)

    @QtCore.Slot(float)
    def switch_on(self, ch):
        return self._generator.generator_on(ch)

    @QtCore.Slot(float)
    def switch_off(self, ch):
        return self._generator.generator_off(ch)