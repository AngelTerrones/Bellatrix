# Copyright (c) 2019 Angel Terrones (<angelterrones@gmail.com>)

import os
import ast
import configparser as cp
from typing import Any


class Configuration:
    """
    Data structure to hold the Core/SoC configuration.

    Args:
    - configFile: Name of the configuration file to load.
    """
    def __init__(self, configFile: str) -> None:
        configFile = os.path.abspath(configFile)
        assert type(configFile) == str and len(configFile), "Please, indicate a valid name for the config file: {0}".format(configFile)
        assert os.path.isfile(configFile), "Configuration file does not exist. Please, indicate an existing file: {0}".format(configFile)

        self.__configFile = configFile
        self.__config     = cp.ConfigParser()
        self.__dict       = {}
        try:
            self.__config.optionxform = str  # type: ignore
            self.__config.read(configFile)
        except Exception:
            assert 0, "Unable to open the config file: {0}".format(configFile)

        sections = self.__config.sections()
        for section in sections:
            try:
                dict1 = self.__getOptionsFromSection(section)
                self.__dict[section] = dict1
            except Exception:
                raise RuntimeError("Unable to parse configuration file: {0}".format(configFile))

    def __getOptionsFromSection(self, section: str) -> dict:
        """
        Extract al the options from the given section, and stores them in a dictionary.
        """
        dict1 = {}
        options = self.__config.options(section)
        for option in options:
            value = self.__config.get(section, option)
            dict1[option] = ast.literal_eval(value)
        return dict1

    def getOption(self, section: str, option: str, default: Any = None) -> Any:
        """
        Get a 'option' for the given 'section'.

        Args:
        - section: Configuration level
        - option:  Option for given section
        - default: In case of error, return this value as default (do not abort execution)

        Returns:
        - configuration value. Example:
          value = config_structure[section][option]
        """
        try:
            return self.__dict[section][option]
        except KeyError:
            raise KeyError("Invalid arguments: section = {0}, option = {1}".format(section, option))
