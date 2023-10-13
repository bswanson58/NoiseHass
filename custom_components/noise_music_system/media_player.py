"""Platform for Noise Music System integration"""
from __future__ import annotations

from pprint import pformat
import voluptuous as vol
import logging
from typing import Any

from homeassistant.components.media_player.const import MediaPlayerEntityFeature

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import ( PLATFORM_SCHEMA, MediaPlayerEntity )
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_COMMAND,
    ATTR_ID,
    CONF_DEVICE_ID,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.json import json_loads

_LOGGER = logging.getLogger("noisemusicsystem")

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string
})

def _slugify_upper(string: str) -> str:
    """Return a slugified version of string, uppercased."""
    return slugify(string).upper()


async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None
    ) -> None:
    """Set up the Noise Music System platform"""

    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return

    _LOGGER.info(pformat(config))

    device = {
        CONF_NAME: config[CONF_NAME],
        CONF_DEVICE_ID: config[CONF_DEVICE_ID]
    }

    async_add_entities([NoiseMusicSystem(device, hass)])


class NoiseMusicSystem(MediaPlayerEntity):
    def __init__(self, device, hass: HomeAssistant) -> None:
        _LOGGER.info(pformat(device))
        self._hass = hass
        self._name = device[CONF_NAME]
        self._device_id = _slugify_upper(device[CONF_DEVICE_ID])
        self._subscribe_topic = "noisemusicsystem/#"

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        def update_availability(payload: str) -> None:
            """Update device availability"""
            online = payload == "online"

        def update_config(payload: str) -> None:
            """Update device configuration"""

        def update_state(payload: str) -> None:
            """Update device state"""

        def device_command(payload: str) -> None:
            """Perform device command"""

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                topic_info = _parse_topic(msg.topic)
                if topic_info.get(CONF_DEVICE_ID) == self._device_id:
                    data = msg.payload
                    command = topic_info.get(ATTR_COMMAND)

                    match command:
                        case 'availability':
                            update_availability(data)
                        case 'config':
                            update_config(data)
                        case 'state':
                            update_state(data)
                        case 'command':
                            device_command(data)

            except vol.MultipleInvalid as error:
                _LOGGER.debug("Skipping update because of malformatted data: %s", error)
                return

        await mqtt.async_subscribe(self.hass, self._subscribe_topic, message_received, 1)

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return super().supported_features

    def update(self) -> None:
        return


def _parse_topic(topic: str) -> dict[str, Any]:
    """Parse the mqtt topic string"""
    parts = topic.split("/")
    if len(parts) < 3:
        return

    device= parts[1]
    command = parts[2]
    device_id = _slugify_upper(device)
    return {ATTR_DEVICE_ID: device_id, ATTR_COMMAND: command}
