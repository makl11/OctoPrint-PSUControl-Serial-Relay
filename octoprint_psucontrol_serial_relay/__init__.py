# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from serial import Serial


class PSUControl_Serial_Relay(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.RestartNeedingPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
):
    DEFAULT_CONFIG = {"port": "", "baudrate": -1}
    config: dict
    serial_relay: Serial | None

    def __init__(self):
        self.config = self.DEFAULT_CONFIG
        self.serial_relay = None

    def __del__(self):
        if self.serial_relay is not None and self.serial_relay.is_open:
            self.serial_relay.close()

    def reload_config(self):
        for k, v in self.DEFAULT_CONFIG.items():
            if type(v) == str:
                v = self._settings.get([k])
            elif type(v) == int:
                v = self._settings.get_int([k])
            elif type(v) == float:
                v = self._settings.get_float([k])
            elif type(v) == bool:
                v = self._settings.get_boolean([k])

            self.config[k] = v
            self._logger.debug("{}: {}".format(k, v))

    def reconnect(self):
        if self.serial_relay is not None and self.serial_relay.is_open:
            self.serial_relay.close()
        self.serial_relay = Serial(self.config["port"], self.config["baudrate"])
        self.serial_relay.open()

    def ensure_connection(self):
        if (
            isinstance(self.serial_relay, Serial)
            and (
                self.serial_relay.port != self.config["port"]
                or self.serial_relay.baudrate != self.config["baudrate"]
                or not self.serial_relay.is_open
            )
        ) or (
            self.serial_relay is None
            and self.config["port"] != ""
            and self.config["baudrate"] > 0
        ):
            self.reconnect()

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
        self.reload_config()
        self.ensure_connection()

    def get_settings_defaults(self):
        return self.DEFAULT_CONFIG

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.reload_config()
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
