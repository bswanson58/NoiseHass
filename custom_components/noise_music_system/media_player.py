"""Platform for Noise Music System integration"""
from __future__ import annotations

import logging
from pprint import pformat
import voluptuous as vol
from homeassistant.components.media_player.const import MediaPlayerEntityFeature

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import ( PLATFORM_SCHEMA, MediaPlayerEntity )
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger("noisemusicsystem")

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string
})

async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None
    ) -> None:
    """Set up the Noise Music System platform"""
    _LOGGER.info(pformat(config))

    device = {
        "name": config[CONF_NAME]
    }

    add_entities([NoiseMusicSystem(device)])


class NoiseMusicSystem(MediaPlayerEntity):
    def __init__(self, device) -> None:
        _LOGGER.info(pformat(device))
        self._name = device["name"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return super().supported_features

    def update(self) -> None:
        return