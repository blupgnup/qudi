# -*- coding: utf-8 -*-

"""
This file contains a gui to see wavemeter data during laser scanning.

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
import numpy as np
import os
import pyqtgraph as pg
import pyqtgraph.exporters

from core.connector import Connector
from core.util import units
from gui.guibase import GUIBase
from gui.colordefs import QudiPalettePale as palette
from gui.fitsettings import FitSettingsDialog, FitSettingsComboBox
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic


class wavemeter(QtWidgets.QMainWindow):
    def __init__(self):
        """ Create the laser scanner window.
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_scanwindow.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class wavemeterGUI(GUIBase):
    """
    """
    # declare connectors
    wavemeter_logic = Connector(interface='WavemeterLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.log.debug('The following configuration was found.')

        # checking for the right configuration
        for key in config.keys():
            self.log.info('{0}: {1}'.format(key,config[key]))

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """

        self.wavemeter_logic = self.cavitylength_logic()

        # setting up the window
        self._mw = wavemeter()

        self._mw.actionStop_resume_scan.triggered.connect(self.stop_resume_clicked)
        self._mw.actionStart_scan.triggered.connect(self.start_clicked)
        self._mw.vacuumButton.setChecked(True)
        self._mw.show()

        self.wavemeter_logic.sig_data_updated.connect(self.updateData, QtCore.Qt.QueuedConnection)
        self._mw.airButton.clicked.connect(self.update_mode)
        self._mw.vacuumButton.clicked.connect(self.update_mode)

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        self._mw.actionStop_resume_scan.triggered.disconnect()
        self._mw.actionStart_scan.triggered.disconnect()
        self.wavemeter_logic.sig_data_updated.disconnect()

        self._mw.close()

    def show(self):
        """ Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def updateData(self, wavelength, frequency):
        """ The function that grabs the data and sends it to the plot.
        """
        self._mw.wavelengthLabel.setText('{0:,.5f} nm '.format(wavelength))
        self._mw.frequencyLabel.setText('{0:,.1f} THz '.format(frequency))

    def stop_resume_clicked(self):
        """ Handling the Start button to stop and restart the counter.
        """
        # If running, then we stop the measurement and enable inputs again
        self.wavemeter_logic.stop_acquisition()
        self._mw.actionStop_resume_scan.setEnabled(False)
        self._mw.actionStart_scan.setEnabled(True)

    def start_clicked(self):

        # Enable the stop button once a scan starts.
        self._mw.actionStop_resume_scan.setText('Stop')
        self._mw.actionStop_resume_scan.setEnabled(True)
        self._mw.actionStart_scan.setEnabled(False)

    def update_mode(self):
        if self.wavemeter_logic.module_state() == 'idle':
            pass
        else:
            self.start_clicked()
