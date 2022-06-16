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
import pyqtgraph as pg
import pyqtgraph.exporters
import datetime

from core.connector import Connector
from core.statusvariable import StatusVar
from core.util import units
from gui.colordefs import QudiPalettePale as palette
from gui.fitsettings import FitSettingsDialog, FitSettingsComboBox
from gui.guibase import GUIBase
from qtpy import QtCore, QtWidgets, uic
from qtwidgets.scientific_spinbox import ScienDSpinBox, ScienSpinBox
from enum import Enum
import matplotlib.pyplot as plt


class ModeSpectrumMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_modespectrum_gui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class ModeSpectrumGUI(GUIBase):
    modespectrumlogic = Connector(interface='ModeSpectrumLogic')
    savelogic = Connector(interface='SaveLogic')

    sigSingleAcquisition = QtCore.Signal(int)
    sigFitChanged = QtCore.Signal(str)
    sigDoFit = QtCore.Signal(str, object, object)
    sigScopeSettings = QtCore.Signal(float, int, float)

    def on_activate(self):
        """ Definition and initialisation of the GUI plus staring the measurement.
        """
        self._mw = ModeSpectrumMainWindow()
        self._modespec = self.modespectrumlogic()
        self._save_logic = self.savelogic()

        # For each channel that the logic has, add a widget to the GUI to show its state
        self._activate_main_window_ui()
        
        # Create a QSettings object for the mainwindow and store the actual GUI layout
        self.mwsettings = QtCore.QSettings("QUDI", "MODESPECTRUM")

        # Add save file tag input box
        self._mw.save_tag_LineEdit = QtWidgets.QLineEdit(self._mw)
        self._mw.save_tag_LineEdit.setMaximumWidth(500)
        self._mw.save_tag_LineEdit.setMinimumWidth(200)
        self._mw.save_tag_LineEdit.setToolTip('Enter a nametag which will be\n'
                                              'added to the filename.')
        self._mw.analysis_ToolBar.addWidget(self._mw.save_tag_LineEdit)

        self.__connect_internal_signals()
        self.__initialize_layout()
        return

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        self._deactivate_main_window_ui()
        self.__disconnect_internal_signals()
        self.mwsettings.setValue("geometry", self._mw.saveGeometry())
        self.mwsettings.setValue("windowState", self._mw.saveState())
        return

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()
        return

    def __connect_internal_signals(self):
        # FIT SETTINGS
        self._fsd = FitSettingsDialog(self._modespec.fc)
        self._fsd.applySettings()

        # CONNECT SIGNALS
        # internal user input
        self._mw.action_single.triggered.connect(self.record_single_trace)
        self._mw.action_open.triggered.connect(self.change_dir)
        self._mw.action_save.triggered.connect(self.save_array_clicked)
        self._mw.action_save_as_pdf.triggered.connect(self.save_pdf_clicked)
        self._mw.actionFit_settings.triggered.connect(self._fsd.show)
        
        # pull default values from logic:
        self._mw.length_doubleSpinBox.setValue(self._modespec.cavity_length)
        self._mw.channel_spinBox.setValue(self._modespec.current_channel)
        self._mw.ROCa_doubleSpinBox.setValue(self._modespec.ROCa)
        self._mw.ROCb_doubleSpinBox.setValue(self._modespec.ROCb)
        
        # control/values-changed signals to logic
        self.sigSingleAcquisition.connect(self._modespec.get_single_trace)
        self.sigDoFit.connect(self._modespec.do_fit)
        
        # Update signals coming from logic:
        self._modespec.sigUpdateGui.connect(self.update_gui)
        self._mw.length_doubleSpinBox.valueChanged.connect(self.update_Spectrum)
        self._mw.ROCa_doubleSpinBox.valueChanged.connect(self.update_Spectrum)
        self._mw.ROCb_doubleSpinBox.valueChanged.connect(self.update_Spectrum)
        self._mw.do_fit_PushButton.clicked.connect(self.doFit)
        self._modespec.sig_fit_updated.connect(self.updateFit, QtCore.Qt.QueuedConnection)
        self._mw.PlotSpectrum_PushButton.clicked.connect(self.update_Spectrum)

        self._mw.show()

        self.record_single_trace()
        return

    def __disconnect_internal_signals(self):
        # internal user input
        self._mw.action_single.triggered.disconnect()
        self._mw.action_open.triggered.disconnect()
        self._mw.action_save.triggered.disconnect()
        self._mw.action_save_as_pdf.triggered.disconnect()
        self._mw.actionFit_settings.triggered.disconnect()

        # control/values-changed signals to logic
        self.sigSingleAcquisition.disconnect()
        self.sigDoFit.disconnect()
        
        # Update signals coming from logic:
        self._modespec.sigUpdateGui.disconnect()
        self._mw.length_doubleSpinBox.valueChanged.disconnect()
        self._mw.ROCa_doubleSpinBox.valueChanged.disconnect()
        self._mw.ROCb_doubleSpinBox.valueChanged.disconnect()
        self._mw.do_fit_PushButton.clicked.disconnect()
        self._modespec.sig_fit_updated.disconnect()
        self._mw.PlotSpectrum_PushButton.clicked.disconnect()

        self._mw.close()
        return

    def __initialize_layout(self):
        self._pw = self._mw.trace_PlotWidget
        self.plot1 = self._pw.plotItem
        self.plot1.setLabel('left', 'voltage', units='V')
        self.plot1.setLabel('bottom', 'time', units='s')
        self.plot1.showButtons()
        self.plot1.setMenuEnabled()

        self._curve1 = pg.PlotDataItem(pen=pg.mkPen(palette.c1), symbol=None)
        self._curve2 = pg.PlotDataItem(pen=pg.mkPen(palette.c3), symbol=None)
        self._curve3 = pg.BarGraphItem(x=[], height=[], width=0, pen=pg.mkPen(palette.c4))
        self.plot1.addItem(self._curve1, clear=True)
        self.plot1.addItem(self._curve2, clear=True)
        self.plot1.addItem(self._curve3, clear=True, alpha=0.2)

    def update_gui(self):
        self._curve1.setData(x=self._modespec.time_axis, y=self._modespec._current_trace, clear=True)

    @QtCore.Slot()
    def update_Spectrum(self):
        self.plot1.enableAutoRange(axis='x', enable=False)
        self.plot1.enableAutoRange(axis='y', enable=False)
        self._modespec.calc_Spectrum(self._mw.length_doubleSpinBox.value(), self._mw.ROCa_doubleSpinBox.value(), self._mw.ROCb_doubleSpinBox.value())
        #self._curve3.setData(x=self._modespec.spectrum_x, y=np.multiply(self._modespec.spectrum_y, self._mw.doubleSpinBox_ampscale.value()), clear=True)
        self._curve3.setOpts(x=self._modespec.spectrum_x, height=np.multiply(self._modespec.spectrum_y, self._mw.doubleSpinBox_ampscale.value()), width=1e-5)

    @QtCore.Slot()
    def doFit(self):
        self.sigDoFit.emit('Two Lorentzian peaks', None, None)

    @QtCore.Slot()
    def updateFit(self):
        """ Update the shown fit. """
        current_fit = self._modespec.fc.current_fit
        result_str_dict = self._modespec.result_str_dict

        self.plot1.setLabel('bottom', 'FSR', units='')
        self._curve1.setData(x=self._modespec.time_axis, y=self._modespec._current_trace, clear=True)
        self._curve2.setData(x=self._modespec.spectrum_fit_x, y=self._modespec.spectrum_fit_y, clear=True)

    ###########################################################################
    #                    Main window related methods                          #
    ###########################################################################
    def _activate_main_window_ui(self):
        self._setup_toolbar()
        return

    def _deactivate_main_window_ui(self):
        pass

    def _setup_toolbar(self):
        # create all the needed control widgets on the fly
        return

    def record_single_trace(self):
        """ Handle resume of the scanning without resetting the data.
        """
        self.sigSingleAcquisition.emit(self._mw.channel_spinBox.value())
        self.doFit()

    def save_pdf_clicked(self):
        timestamp = datetime.datetime.now()
        filetag = self._mw.save_tag_LineEdit.text()

        self._modespec.save_fig(filetag, timestamp)
        self.log.info('cavity figure saved to:\n{0}'.format(self._modespec.dirname))

    def save_array_clicked(self):
        timestamp = datetime.datetime.now()
        filetag = self._mw.save_tag_LineEdit.text()

        self._modespec.save_data(filetag, timestamp)
        self.log.info('cavity data saved to:\n{0}'.format(self._modespec.dirname))

    def change_dir(self):
        dirname = QtWidgets.QFileDialog.getExistingDirectory(self._mw,
                                                            "Save to :", "",
                                                            QtWidgets.QFileDialog.ShowDirsOnly |
                                                            QtWidgets.QFileDialog.DontResolveSymlinks)
        self._modespec.dirname = os.path.normpath(dirname)
        