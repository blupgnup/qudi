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


from core.interface import abstract_interface_method
from core.meta import InterfaceMetaclass
from enum import Enum


class FrequencyGeneratorInterface(metaclass=InterfaceMetaclass):
    """ Interface class to define the abstract controls and
    communication with all pulsing devices.
    """

    @abstract_interface_method
    def generator_on(self, ch=None):
        """ Switches the pulsing device on.

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abstract_interface_method
    def generator_off(self, ch=None):
        """ Switches the pulsing device off.

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abstract_interface_method
    def set_power_level(self, amplitude=None, ch=None):
        pass

    @abstract_interface_method
    def set_frequency(self, freq=None, ch=None):
        pass

    @abstract_interface_method
    def get_power_level(self, ch=None):
        pass
  
    @abstract_interface_method
    def get_frequency(self, ch=None):
        pass

    @abstract_interface_method
    def set_phase(self, phase=None, ch=None):
        pass
    
    @abstract_interface_method
    def get_phase(self, ch=None):
        pass

    @abstract_interface_method
    def get_temp(self, ch=None):
        pass
    
    @abstract_interface_method
    def get_active_channels(self):
        pass