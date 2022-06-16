# -*- coding: utf-8 -*-

"""
This file contains a Qudi gui module for quick plotting.

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

import os
import numpy as np
from itertools import cycle
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic
import pyqtgraph as pg

from gui.colordefs import QudiPalettePale as palette
from core.connector import Connector
from gui.guibase import GUIBase


class FinesseMainWindow(QtWidgets.QMainWindow):

    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_finesse_gui.ui')

        # Load it
        super(FinesseMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()


class FinesseGui(GUIBase):
    """ FIXME: Please document
    """
    # declare connectors
    finessecalclogic = Connector(interface='FinesseCalcLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        self._finesse = self.finessecalclogic()

        #####################
        # Configuring the dock widgets
        # Use the inherited class 'CounterMainWindow' to create the GUI window
        self._mw = FinesseMainWindow()

        # Setup dock widgets
        self._mw.centralwidget.hide()
        self._mw.setDockNestingEnabled(True)

        # Plot labels.
        self._mw.finesse_value.setText('<font color={0}>0</font>'.format(palette.c3.name()))
        self._pw = self._mw.qdplot_PlotWidget

        self._pw.setLabel('left', 'finesse', units='')
        self._pw.setLabel('bottom', 'choose variable', units='?')
        self._pw.setLabel('bottom', 'T1', units='ppm')
        self._curve = pg.PlotWidget()

        self.__connect_internal_signals()

        self.updateScattering()
        self.updateClipping()

    def __connect_internal_signals(self):
        #####################
        # Setting default parameters
        self._mw.spinBox_fiberdiameter.setValue(self._finesse.fiber_dia)
        self._mw.spinBox_ROCa.setValue(self._finesse.ROCa)
        self._mw.spinBox_ROCb.setValue(self._finesse.ROCb)
        self._mw.spinBox_CavityLength.setValue(self._finesse.cavity_length)

        self._mw.doubleSpinBox_RMS.setValue(self._finesse.rms)

        self._mw.spinBox_T1.setValue(self._finesse.T1)
        self._mw.spinBox_T2.setValue(self._finesse.T2)
        self._mw.spinBox_La.setValue(self._finesse.La)

        #####################
        # Connecting user interactions
        self._mw.spinBox_fiberdiameter.editingFinished.connect(self.updateClipping)
        self._mw.spinBox_ROCa.editingFinished.connect(self.updateClipping)
        self._mw.spinBox_ROCb.editingFinished.connect(self.updateClipping)
        self._mw.spinBox_CavityLength.editingFinished.connect(self.updateClipping)

        self._mw.doubleSpinBox_RMS.editingFinished.connect(self.updateScattering)
        self._mw.radioButton_standard.toggled.connect(self.updateScattering)
        self._mw.radioButton_standardangle.toggled.connect(self.updateScattering)
        self._mw.radioButton_advanced.toggled.connect(self.updateScattering)

        self._mw.spinBox_T1.editingFinished.connect(self.updateFinesse)
        self._mw.spinBox_T2.editingFinished.connect(self.updateFinesse)
        self._mw.spinBox_La.editingFinished.connect(self.updateFinesse)

        self._mw.radioButton_cavitylength.toggled.connect(self.updatePlot)
        self._mw.radioButton_mirrordia.toggled.connect(self.updatePlot)
        self._mw.radioButton_T1.toggled.connect(self.updatePlot)
        self._mw.radioButton_T2.toggled.connect(self.updatePlot)
        self._mw.radioButton_La.toggled.connect(self.updatePlot)

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate the module
        """
        self._mw.close()

    def updateScattering(self):
        if self._mw.radioButton_standard.isChecked() is True:
            ls = self._finesse.calc_scattering_simple(self._mw.doubleSpinBox_RMS.value())
        elif self._mw.radioButton_standardangle.isChecked() is True:
            ls = self._finesse.calc_scattering_simpleangle(self._mw.doubleSpinBox_RMS.value())
        elif self._mw.radioButton_advanced.isChecked() is True:
            ls = self._finesse.calc_scattering_advanced(self._mw.doubleSpinBox_RMS.value())
        self._mw.LS_label.setText('{0:,.2f}'.format(ls))
        self.updateFinesse()
        self.updatePlot()

    def updateClipping(self):
        self._finesse.cavity_length = self._mw.spinBox_CavityLength.value()
        self._finesse.fiber_dia = self._mw.spinBox_fiberdiameter.value()
        self._finesse.ROCa = self._mw.spinBox_ROCa.value()
        self._finesse.ROCb = self._mw.spinBox_ROCb.value()
        lc = self._finesse.calc_clipping(self._mw.spinBox_CavityLength.value(),
                                         self._mw.spinBox_fiberdiameter.value(),
                                         self._mw.spinBox_ROCa.value(),
                                         self._mw.spinBox_ROCb.value())
        self._mw.LC_label.setText('{0:,.2f}'.format(lc))
        self.updateFinesse()
        self.updatePlot()

    def updateFinesse(self):
        """ Function creates empty plots, grabs the data and sends it to them.
        """
        self._finesse.T1 = self._mw.spinBox_T1.value()
        self._finesse.T2 = self._mw.spinBox_T2.value()
        self._finesse.La = self._mw.spinBox_La.value()
        finesse = self._finesse.calc_finesse(self._mw.spinBox_T1.value(),
                                             self._mw.spinBox_T2.value(),
                                             self._mw.spinBox_La.value())
        self._mw.finesse_value.setText('<font color={0}>{1:,.0f} ± 0</font>'.format(palette.c3.name(), finesse))
        self.updatePlot()

    def updatePlot(self):
        if self._mw.radioButton_cavitylength.isChecked() is True:
            self._pw.setLabel('bottom', 'cavity length', units='µm')
            xdata = np.linspace(0.9*self._mw.spinBox_CavityLength.value(),
                                1.1*self._mw.spinBox_CavityLength.value(), 100)
            self._pw.plot(xdata, self._finesse.plot_finesse_fiber(xdata,
                                                                  self._mw.spinBox_fiberdiameter.value()),
                          clear=True, pen=pg.mkPen(palette.c1))

        elif self._mw.radioButton_mirrordia.isChecked() is True:
            self._pw.setLabel('bottom', 'fiber mirror diameter', units='µm')
            xdata = np.linspace(0.9*self._mw.spinBox_fiberdiameter.value(),
                                1.1*self._mw.spinBox_fiberdiameter.value(), 100)
            self._pw.plot(xdata, self._finesse.plot_finesse_fiber(self._mw.spinBox_CavityLength.value(),
                                                                  xdata),
                          clear=True, pen=pg.mkPen(palette.c1))
        
        elif self._mw.radioButton_T1.isChecked() is True:
            self._pw.setLabel('bottom', 'T1', units='ppm')
            xdata = np.linspace(self._mw.spinBox_T1.value()/2,
                                1.5*self._mw.spinBox_T1.value(), 100)
            self._pw.plot(xdata, self._finesse.calc_finesse(xdata,
                                                            self._mw.spinBox_T2.value(),
                                                            self._mw.spinBox_La.value()),
                          clear=True, pen=pg.mkPen(palette.c1))

        elif self._mw.radioButton_T2.isChecked() is True:
            self._pw.setLabel('bottom', 'T2', units='ppm')
            xdata = np.linspace(self._mw.spinBox_T2.value()/2,
                                1.5*self._mw.spinBox_T2.value(), 100)
            self._pw.plot(xdata, self._finesse.calc_finesse(self._mw.spinBox_T1.value(),
                                                            xdata,
                                                            self._mw.spinBox_La.value()),
                          clear=True, pen=pg.mkPen(palette.c1))

        elif self._mw.radioButton_La.isChecked() is True:
            self._pw.setLabel('bottom', 'La', units='ppm')
            xdata = np.linspace(self._mw.spinBox_La.value()/2,
                                1.5*self._mw.spinBox_La.value(), 100)
            self._pw.plot(xdata, self._finesse.calc_finesse(self._mw.spinBox_T1.value(),
                                                            self._mw.spinBox_T2.value(),
                                                            xdata),
                          clear=True, pen=pg.mkPen(palette.c1))



