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


class FinesseMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_FinesseMeasurement_gui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class FinesseMeasurementGUI(GUIBase):
    finesselogic = Connector(interface='FinesseLogic')
    savelogic = Connector(interface='SaveLogic')

    sigSingleAcquisition = QtCore.Signal(int)
    sigStartAcquisition = QtCore.Signal(int, float)
    sigStopAcquisition = QtCore.Signal()
    sigFitChanged = QtCore.Signal(str)
    sigDoFit = QtCore.Signal(str, object, object, float)
    sigScopeSettings = QtCore.Signal(float, int, float)
    finesse_average = []

    def on_activate(self):
        """ Definition and initialisation of the GUI plus staring the measurement.
        """
        self._mw = FinesseMainWindow()
        self._finesse = self.finesselogic()
        self._save_logic = self.savelogic()

        # For each channel that the logic has, add a widget to the GUI to show its state
        self._activate_main_window_ui()
        
        # Create a QSettings object for the mainwindow and store the actual GUI layout
        self.mwsettings = QtCore.QSettings("QUDI", "FINESSEMEASUREMENT")
        self.mwsettings.setValue("geometry", self._mw.saveGeometry())
        self.mwsettings.setValue("windowState", self._mw.saveState())

        # Add save file tag input box
        self._mw.save_tag_LineEdit = QtWidgets.QLineEdit(self._mw)
        self._mw.save_tag_LineEdit.setMaximumWidth(500)
        self._mw.save_tag_LineEdit.setMinimumWidth(200)
        self._mw.save_tag_LineEdit.setToolTip('Enter a nametag which will be\n'
                                              'added to the filename.')
        self._mw.analysis_ToolBar.addWidget(self._mw.save_tag_LineEdit)

        self.__connect_internal_signals()
        self.__initialize_layout()

        self.update_FSR()
        return

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        self._deactivate_main_window_ui()
        self.__disconnect_internal_signals()
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
        self._fsd = FitSettingsDialog(self._finesse.fc)
        self._fsd.sigFitsUpdated.connect(self._mw.fit_methods_ComboBox.setFitFunctions)
        self._fsd.applySettings()

        # CONNECT SIGNALS
        # internal user input
        self._mw.action_single.triggered.connect(self.record_single_trace)
        self._mw.action_runcontinous.triggered.connect(self.start_clicked)
        self._mw.action_stop.triggered.connect(self.stop_clicked)
        self._mw.action_open.triggered.connect(self.change_dir)
        self._mw.action_save.triggered.connect(self.save_array_clicked)
        self._mw.action_save_as_pdf.triggered.connect(self.save_pdf_clicked)
        self._mw.actionFit_settings.triggered.connect(self._fsd.show)
        self._mw.doubleSpinBoxVS.editingFinished.connect(self.updateScopeSettings)
        self._mw.doubleSpinBoxRL.editingFinished.connect(self.updateScopeSettings)
        self._mw.doubleSpinBoxAQT.editingFinished.connect(self.updateScopeSettings)
        self._mw.doubleSpinBox_EOM.editingFinished.connect(self.update_EOM_freq)

        # pull default values from logic:
        self._mw.doubleSpinBox_Length.setValue(self._finesse.cavity_length)
        self._mw.channel_spinBox.setValue(self._finesse.current_channel)
        self._mw.doubleSpinBoxVS.setValue(self._finesse.vertical_scale*1e3)
        self._mw.doubleSpinBoxRL.setValue(self._finesse.record_length)
        self._mw.doubleSpinBoxAQT.setValue(self._finesse.time_base*1e3)
        self._mw.refresh_spinBox.setValue(self._finesse.refresh_timing)
        self._mw.doubleSpinBox_EOM.setValue(self._finesse.eom_frequency)

        # control/values-changed signals to logic
        self.sigSingleAcquisition.connect(self._finesse.get_single_trace)
        self.sigStartAcquisition.connect(self._finesse.start_acquisition)
        self.sigStopAcquisition.connect(self._finesse.stop_acquisition)
        self.sigScopeSettings.connect(self._finesse.scope_stetting)
        self.sigDoFit.connect(self._finesse.do_fit)
        self.sigFitChanged.connect(self._finesse.fc.set_current_fit)
        # Update signals coming from logic:
        self._finesse.sigUpdateGui.connect(self.update_gui)
        self._mw.doubleSpinBox_Length.editingFinished.connect(self.update_FSR)
        self._mw.doubleSpinBox_ELength.editingFinished.connect(self.update_FSR)
        self._mw.do_fit_PushButton.clicked.connect(self.doFit)
        self._finesse.sig_fit_updated.connect(self.updateFit, QtCore.Qt.QueuedConnection)
        self._finesse.sig_Parameter_Updated.connect(self.update_parameter,
                                                     QtCore.Qt.QueuedConnection)
        
        self._mw.show()

        self.record_single_trace()
        return

    def __disconnect_internal_signals(self):
       # CONNECT SIGNALS
        # internal user input
        self._mw.action_single.triggered.disconnect()
        self._mw.action_runcontinous.triggered.disconnect()
        self._mw.action_stop.triggered.disconnect()
        self._mw.actionFit_settings.triggered.disconnect()
        self._mw.doubleSpinBoxVS.editingFinished.disconnect()
        self._mw.doubleSpinBoxRL.editingFinished.disconnect()
        self._mw.doubleSpinBoxAQT.editingFinished.disconnect()
        self._mw.doubleSpinBox_EOM.editingFinished.disconnect()

        self.sigSingleAcquisition.disconnect()
        self.sigStartAcquisition.disconnect()
        self.sigStopAcquisition.disconnect()
        self.sigScopeSettings.disconnect()
        self.sigDoFit.disconnect()
        self.sigFitChanged.disconnect()

        self._finesse.sigUpdateGui.disconnect()
        self._mw.doubleSpinBox_Length.editingFinished.disconnect()
        self._mw.doubleSpinBox_ELength.editingFinished.disconnect()
        self._mw.do_fit_PushButton.clicked.disconnect()
        self._finesse.sig_fit_updated.disconnect()
        self._finesse.sig_Parameter_Updated.disconnect()
        
        self._mw.close()
        return

    def __initialize_layout(self):
        #self._mw.Finesse_Label.setText('<font color={0}>Finesse</font>'.format(palette.c3.name()))
        self._mw.FinesseValue_Label.setText('<font color={0}>0</font>'.format(palette.c4.name()))
        
        self._pw = self._mw.trace_PlotWidget
        self.plot1 = self._pw.plotItem
        self.plot1.setLabel('left', 'voltage', units='V')
        self.plot1.setLabel('bottom', 'time', units='s')
        self.plot1.showAxis('right')
        self.plot1.showAxis('top')
        self.plot1.showButtons()
        self.plot1.setMenuEnabled()

        self._curve1 = pg.PlotDataItem(pen=pg.mkPen(palette.c1), symbol=None)
        self._curve2 = pg.PlotDataItem(pen=pg.mkPen(palette.c3), symbol=None)
        self.plot1.addItem(self._curve1, clear=True)
        self.plot1.addItem(self._curve2, clear=True)

    def updateScopeSettings(self):
        if self._mw.action_stop.setEnabled is True:
            self.sigStopAcquisition.emit()
            self.sigScopeSettings.emit(self._mw.doubleSpinBoxAQT.value()*1e-3, self._mw.doubleSpinBoxRL.value(), self._mw.doubleSpinBoxVS.value()*1e-3)
            self.sigStartAcquisition.emit(self._mw.channel_spinBox.value(),
                                        self._mw.refresh_spinBox.value())
        else:
            self.sigScopeSettings.emit(self._mw.doubleSpinBoxAQT.value()*1e-3, self._mw.doubleSpinBoxRL.value(), self._mw.doubleSpinBoxVS.value()*1e-3)

    def update_EOM_freq(self):
        self._finesse.eom_frequency = self._mw.doubleSpinBox_EOM.value()

    def update_gui(self):
        self._curve1.setData(x=self._finesse.time_axis, y=self._finesse._current_trace, clear=True)
        if self._mw.checkBox_Fit.isChecked():
            self.doFit()

    def update_parameter(self, param_dict):
        param = param_dict.get('cavity_length')
        if param is not None:
            self._mw.doubleSpinBox_Length.blockSignals(True)
            self._mw.doubleSpinBox_Length.setValue(param)
            self._mw.doubleSpinBox_Length.blockSignals(False)
        return

    @QtCore.Slot()
    def update_FSR(self):
        (FSR, error) = self._finesse.calc_FSR(self._mw.doubleSpinBox_Length.value(), self._mw.doubleSpinBox_ELength.value())
        self._mw.FSRValue_Label.setText('<font color={0}>{1:,.2f} ± {2:,.2f} GHz</font>'.format(
                                             palette.c2.name(), FSR, error))
        #self._mw.FSRValue_Label.setText('{0:,.2f} GHz'.format(FSR))

    @QtCore.Slot()
    def doFit(self):
        self._mw.ready_label.setText('<font color=red>fitting...</font>')
        fit_function = self._mw.fit_methods_ComboBox.getCurrentFit()[0]
        self.sigFitChanged.emit(fit_function)
        self.sigDoFit.emit(fit_function, None, None, self._mw.doubleSpinBox_chi.value())

    @QtCore.Slot()
    def updateFit(self):
        """ Update the shown fit. """
        current_fit = self._finesse.fc.current_fit
        result_str_dict = self._finesse.result_str_dict
        #fit_param = self._wm_logger_logic.fc.current_fit_param
        if current_fit != 'No Fit':
            # display results as formatted text
            self._mw.fit_results_DisplayWidget.clear()
            try:
                formated_results = units.create_formatted_output(result_str_dict)
            except:
                formated_results = 'this fit does not return formatted results'
            self._mw.fit_results_DisplayWidget.setPlainText(formated_results)

        if current_fit is not None:
            self._mw.fit_methods_ComboBox.blockSignals(True)
            self._mw.fit_methods_ComboBox.setCurrentFit(current_fit)
            self._mw.fit_methods_ComboBox.blockSignals(False)
        
        self._curve2.setData(x=self._finesse.cavity_fit_x, y=self._finesse.cavity_fit_y, clear=True)
        if self._mw.checkBox_average.isChecked() is True:
            if self._finesse.cavity_finesse > 0:
                self.finesse_average.append(self._finesse.cavity_finesse)
                if len(self.finesse_average) > self._mw.spinBox_numAverage.value():
                    del self.finesse_average[0]
                self._mw.FinesseValue_Label.setText('<font color={0}>{1:,.1f} ± {2:,.1f}</font>'.format(palette.c4.name(), np.mean(self.finesse_average), np.std(self.finesse_average))) 
        else:
            self._mw.FinesseValue_Label.setText('<font color={0}>{1:,.1f} ± {2:,.1f}</font>'.format(palette.c4.name(), self._finesse.cavity_finesse, self._finesse.cavity_finesse_error))
        self._mw.ready_label.setText('<font color=green>ready</font>')


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

    def start_clicked(self):
        """ Handling the Start button to stop and restart the counter.
        """
        self.sigStartAcquisition.emit(self._mw.channel_spinBox.value(),
                                      self._mw.refresh_spinBox.value())
        self._mw.action_runcontinous.setEnabled(False)
        self._mw.action_single.setEnabled(False)
        self._mw.action_stop.setEnabled(True)

    def stop_clicked(self):
        """ Handling the Start button to stop and restart the counter.
        """
        self.sigStopAcquisition.emit()
        self._mw.action_runcontinous.setEnabled(True)
        self._mw.action_single.setEnabled(True)
        self._mw.action_stop.setEnabled(False)

    def save_pdf_clicked(self):
        timestamp = datetime.datetime.now()
        filetag = self._mw.save_tag_LineEdit.text()

        self._finesse.save_fig(filetag, timestamp)
        self.log.info('cavity figure saved to:\n{0}'.format(self._finesse.dirname))

    def save_array_clicked(self):
        timestamp = datetime.datetime.now()
        filetag = self._mw.save_tag_LineEdit.text()

        self._finesse.save_data(filetag, timestamp)
        self.log.info('cavity data saved to:\n{0}'.format(self._finesse.dirname))

    def change_dir(self):
        dirname = QtWidgets.QFileDialog.getExistingDirectory(self._mw,
                                                            "Save to :", "",
                                                            QtWidgets.QFileDialog.ShowDirsOnly |
                                                            QtWidgets.QFileDialog.DontResolveSymlinks)
        self._finesse.dirname = os.path.normpath(dirname)
        