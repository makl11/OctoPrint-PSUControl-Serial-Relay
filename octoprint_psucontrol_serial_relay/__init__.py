# coding=utf-8
from __future__ import absolute_import

from dataclasses import InitVar, dataclass, fields

from serial import Serial

import octoprint.plugin
import octoprint.settings


@dataclass
class PluginConfig:
    owner: InitVar[octoprint.plugin.SettingsPlugin]

    def reload(self):
        for f in fields(self):
            if f.type == str:
                v = self.owner._settings.get([f.name])
            elif f.type == int:
                v = self.owner._settings.get_int([f.name])
            elif f.type == float:
                v = self.owner._settings.get_float([f.name])
            elif f.type == bool:
                v = self.owner._settings.get_boolean([f.name])
            else:
                raise TypeError(f"Fields of type {f.type} are not supported in a Config")
            self[f.name] = v

    def __post_init__(self, owner):
        self.owner = owner

    def __iter__(self):
        return ((f.name, getattr(self, f.name, None)) for f in fields(self))

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)


class PSUControl_Serial_Relay(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.RestartNeedingPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
):
    @dataclass
    class Config(PluginConfig):
        port: str = "Disabled"
        baudrate: int = 9600

    config: Config
    serial_relay: Serial | None

    def __init__(self):
        self.config = self.Config(owner=self)
        self.serial_relay = None

    def __del__(self):
        if self.serial_relay is not None and self.serial_relay.is_open:
            self.serial_relay.close()

    def ensure_connection(self):
        if self.serial_relay is None:
            if self.config.port != "Disabled" and self.config.baudrate > 0:
                self.serial_relay = Serial(self.config.port, self.config.baudrate)
        else:
            if not self.serial_relay.is_open:
                self.serial_relay.open()

            if self.serial_relay.baudrate != self.config.baudrate:
                self.serial_relay.baudrate = self.config.baudrate

            if self.serial_relay.port != self.config.port:
                if self.config.port == "Disabled":
                    self.serial_relay.close()
                    self.serial_relay = None
                else:
                    self.serial_relay.port = self.config.port

    # PSUControl
    def on_startup(self, host, port):
        psucontrol_helpers = self._plugin_manager.get_helpers("psucontrol")
        if not psucontrol_helpers or "register_plugin" not in psucontrol_helpers.keys():
            self._logger.warning(
                "The version of PSUControl that is installed does not support plugin registration."
            )
            return

        self._logger.debug("Registering plugin with PSUControl")
        psucontrol_helpers["register_plugin"](self)

    def turn_psu_on(self):
        self.ensure_connection()
        if self.serial_relay is None:
            return
        self.serial_relay.write(b"\x01")

    def turn_psu_off(self):
        self.ensure_connection()
        if self.serial_relay is None:
            return
        self.serial_relay.write(b"\x00")

    def get_psu_state(self) -> bool:
        self.ensure_connection()
        if self.serial_relay is None:
            return False
        self.serial_relay.write(b"\x03")
        return self.serial_relay.read() == b"\x01"

    # Settings
    def on_settings_initialized(self):
        self.config.reload()
        self.ensure_connection()

    def get_settings_defaults(self):
        return {k: v for k, v in self.Config(owner=self)}

    def on_settings_save(self, data):
        # TODO: Remove this hack by using a custom viewmodel
        if "port" in data and data["port"] is None:
            data["port"] = "Disabled"
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.config.reload()
        self.ensure_connection()

    def get_settings_version(self):
        return 1

    def on_settings_migrate(self, target, current=None):
        pass

    # Template
    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=False)]

    # Auto updates
    def get_update_information(self):
        return {
            "psucontrol_serial_relay": {
                "displayName": "PSU Control - Serial Relay",
                "displayVersion": self._plugin_version,
                # version check: github repository
                "type": "github_release",
                "user": "makl11",
                "repo": "OctoPrint-PSUControl-Serial-Relay",
                "prerelease": "True",
                "current": self._plugin_version,
                # update method: pip
                "pip": "https://github.com/makl11/OctoPrint-PSUControl-Serial-Relay/archive/{target_version}.zip",
            }
        }


__plugin_name__ = "PSU Control - Serial Relay"
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PSUControl_Serial_Relay()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
