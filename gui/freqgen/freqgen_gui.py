# -*- coding: utf-8 -*-

"""
This file contains a gui for the laser controller logic.

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

import numpy as np
import os
import time

from core.connector import Connector
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic


class FrequencyGeneratorWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_freqgen_gui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class FrequencyGeneratorGUI(GUIBase):
    ## declare connectors
    generatorlogic = Connector(interface='FrequencyGeneratorLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI plus staring the measurement.
        """
        self._generator_logic = self.generatorlogic()
        self._mw = FrequencyGeneratorWindow()
        self.__connect_internal_signals()
        
        self._mw.freqSpinBox.setValue(self._generator_logic.ch1_freq/1e6)
        self._mw.freqSpinBox_2.setValue(self._generator_logic.ch2_freq/1e6)
        self._mw.powerSpinBox.setValue(self._generator_logic.ch1_pwr)
        self._mw.powerSpinBox_2.setValue(self._generator_logic.ch2_pwr)
        self._mw.phaseSpinBox.setValue(self._generator_logic.ch1_phase)
        self._mw.phaseSpinBox_2.setValue(self._generator_logic.ch2_phase)
        
        self._mw.show()

        self.updateGui()

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        self._generator_logic.switch_off(0)
        self._generator_logic.switch_off(1)
        self.__disconnect_internal_signals()
        self._mw.close()

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def __connect_internal_signals(self):
        self._generator_logic.sigUpdate.connect(self.updateTempGui)
        self._mw.setvaluesButton.clicked.connect(self.transferValues_0)
        self._mw.setvaluesButton_2.clicked.connect(self.transferValues_1)
        self._mw.rfButton.clicked.connect(self.switchPower_0)
        self._mw.rfButton_2.clicked.connect(self.switchPower_1)
        return

    def __disconnect_internal_signals(self):
        self._generator_logic.sigUpdate.disconnect()
        self._mw.setvaluesButton.clicked.disconnect()
        self._mw.setvaluesButton_2.clicked.disconnect()
        self._mw.rfButton.clicked.disconnect()
        self._mw.rfButton_2.clicked.disconnect()
        return

    def transferValues_0(self):
        self._generator_logic.set_frequency(0, self._mw.freqSpinBox.value()*1e6)
        self._generator_logic.set_power(0, self._mw.powerSpinBox.value())
        self._generator_logic.set_phase(0, self._mw.phaseSpinBox.value())
        self.updateGui()

    def transferValues_1(self):
        self._generator_logic.set_frequency(1, self._mw.freqSpinBox_2.value()*1e6)
        self._generator_logic.set_power(1, self._mw.powerSpinBox_2.value())
        self._generator_logic.set_phase(1, self._mw.phaseSpinBox_2.value())
        self.updateGui()

    def switchPower_0(self):
        if self._mw.rfButton.isChecked() is False:
            self._generator_logic.switch_off(0)
        else:
            self._generator_logic.switch_on(0)
        self.updateGui()

    def switchPower_1(self):
        if self._mw.rfButton_2.isChecked() is False:
            self._generator_logic.switch_off(1)
        else:
            self._generator_logic.switch_on(1)
        self.updateGui()

    def updateGui(self):
        self._mw.freqLabel.setText('{0:6.1f} MHz'.format(self._generator_logic.read_frequency(0)/1e6))
        self._mw.freqLabel_2.setText('{0:6.1f} MHz'.format(self._generator_logic.read_frequency(1)/1e6))
        self._mw.powerLabel.setText('{0:6.1f} dBm'.format(self._generator_logic.read_power(0)))
        self._mw.powerLabel_2.setText('{0:6.1f} dBm'.format(self._generator_logic.read_power(1)))
        self._mw.phaseLabel.setText('{0:6.1f} °'.format(self._generator_logic.read_phase(0)))
        self._mw.phaseLabel_2.setText('{0:6.1f} °'.format(self._generator_logic.read_phase(1)))

    def updateTempGui(self):
        self._mw.tempLabel.setText('{0:6.2f} °C'.format(self._generator_logic.tempch1))
        self._mw.tempLabel_2.setText('{0:6.2f} °C'.format(self._generator_logic.tempch2))
