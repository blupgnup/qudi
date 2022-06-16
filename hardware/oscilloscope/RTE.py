# -*- coding: utf-8 -*-
"""

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
import pyvisa as visa
from time import sleep

from qtpy import QtCore
from core.module import Base
from core.configoption import ConfigOption
from core.util.mutex import Mutex
from interface.oscilloscope_interface import OscilloscopeInterface

class HardwarePull(QtCore.QObject):
    """ Helper class for running the hardware communication in a separate thread. """

    # signal to deliver the wavelength to the parent class
    sig_trace = QtCore.Signal(list)

    def __init__(self, parentclass):
        super().__init__()

        # remember the reference to the parent class to access functions ad settings
        self._parentclass = parentclass

    def handle_timer(self, state_change, channel):
        """ Threaded method that can be called by a signal from outside to start the timer.
        @param bool state: (True) starts timer, (False) stops it.
        """
        self.channel = channel
        if state_change:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self._measure_thread)
            self.timer.start(self._parentclass._measurement_timing)
        else:
            if hasattr(self, 'timer'):
                self.timer.stop()

    def _measure_thread(self):
        """ The threaded method querying the data from the scope.
        """
        # update as long as the state is busy
        if self._parentclass.module_state() == 'running':
            trace = self._parentclass._rte.query_binary_values('FORM REAL,32;:CHAN{}:DATA?'.format(self.channel),
                                                               datatype='f', is_big_endian=False)
            # send the data to the parent via a signal
            self.sig_trace.emit(trace)


class RohdeSchwarz(Base, OscilloscopeInterface):
    _address = ConfigOption('address', missing='error')
    _rto = None
    _visa_timeout = ConfigOption('visa_timeout', default=1000.)
    _opc_timeout = ConfigOption('opc_timeout', default=3000.)
    _measurement_timing = ConfigOption('measurement_timing', default=300.)

    sig_handle_timer = QtCore.Signal(bool, int)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        #locking for thread safety
        self.threadlock = Mutex()
        
        self._current_trace = []

    def on_activate(self):
        """ Startup the module """
        try:
            rm = visa.ResourceManager()
            rm.list_resources()

            self._rte = rm.open_resource(self._address)
            print(self._rte.query('*IDN?'))
            self._rte.write_termination = ''
            self._rte.timeout = 5000
            self._rte.write('SING')
            self._rte.query('*OPC?')
            self._rte.write('EXPort:WAVeform:FASTexport ON')
            self._rte.query('*OPC?')
            self._rte.write("SYST:DISP:UPD ON")
            self._rte.query('*OPC?')
            self._rte.write('SYSTem:KLOCk OFF')
            self._rte.write('RUNContinous')
        except Exception as ex:
            print('Error initializing the instrument session:\n' + ex.args[0])
            exit()
        
        self.hardware_thread = QtCore.QThread()
        self._hardware_pull = HardwarePull(self)
        self._hardware_pull.moveToThread(self.hardware_thread)
        self.sig_handle_timer.connect(self._hardware_pull.handle_timer)
        self._hardware_pull.sig_trace.connect(self.handle_trace)
        self.hardware_thread.start()

    def on_deactivate(self):
        """ Stops the module """
        self._rte.close()
        self.hardware_thread.quit()
        self.sig_handle_timer.disconnect()
        self._hardware_pull.sig_trace.disconnect()

    def handle_trace(self, trace):
        """ Function to save the wavelength, when it comes in with a signal.
        """
        self._current_trace = trace

    def getData(self, channel):
        return self._current_trace

    def getData_cont(self, channel):
        trace = self._rte.query_binary_values('FORM REAL,32;:CHAN{}:DATA?'.format(channel),
                                              datatype='f', is_big_endian=False)
        self._current_trace = trace
        return self._current_trace

    def RunContinous(self, channel=1, refreshrate=None):
        """ SimpleDataInterface function to get the power from the scope """
        self._rte.write('RUNContinous')
        self._rte.query('*OPC?')
        '''
        if refreshrate is not None:
            self._measurement_timing = refreshrate
        if self.module_state() == 'running':
            self.log.error('Scope busy')
            return -1
        self.module_state.run()
        self.sig_handle_timer.emit(True, channel)
        '''
        return 0

    def SetVerticalScale(self, channel=1, scale=10e-3):
        self._rte.write('CHAN{0}:SCAL {1}'.format(channel, scale))

    def SetTimeBase(self, timebase=5e-3):
        self._rte.write('TIMebase:RANGe {}'.format(timebase))

    def SetRecordLength(self, recordlength=1000):
        self._rte.write('ACQ:POIN {}'.format(recordlength))
        sleep(0.1)

    def RunSingle(self, channel=1):
        #self._rte.write('RUNSingle')
        trace = self._rte.query_binary_values('FORM REAL,32;:CHAN{}:DATA?'.format(channel),
                                              datatype='f', is_big_endian=False)
        return trace    

    def RunSTOP(self):
        if self.module_state() == 'idle':
            self.log.warning('Scope was already stopped, stopping it '
                    'anyway!')
        else:
            self.sig_handle_timer.emit(False, None)
            self.module_state.stop()
        return 0

    def get_xaxis(self):
        timebase = float(self._rte.query('TIMebase:RANGe?'))
        self._rte.query('*OPC?')
        recordlength = int(self._rte.query('ACQ:POIN?'))
        self._rte.query('*OPC?')
        xaxis = np.linspace(-timebase/2, timebase/2, recordlength)
        return xaxis
