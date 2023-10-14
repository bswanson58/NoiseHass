"""Platform for Noise Music System integration"""
from __future__ import annotations

import datetime as dt
from pprint import pformat
import voluptuous as vol
import logging
from typing import Any

from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,)

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerDeviceClass,
    RepeatMode,
    MediaPlayerState,
    MediaType
)
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_COMMAND,
    ATTR_ID,
    CONF_DEVICE_ID,
    CONF_NAME
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

SUPPORT_FEATURES = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
)

SUBSCRIBE_TOPIC = "noisemusicsystem/#"

ATTR_ARTIST = 'artist'
ATTR_ALBUM = 'album'
ATTR_TRACKNAME = 'trackname'
ATTR_TRACK_NUMBER = 'tracknumber'
ATTR_DURATION = 'duration'
ATTR_POSITION = 'position'
ATTR_VOLUME = 'volume'

STATUS_PAYLOAD = vol.Schema(
    vol.All(
        json_loads,
        vol.Schema(
            {
                vol.Optional(ATTR_ARTIST): cv.string,
                vol.Optional(ATTR_ALBUM): cv.string,
                vol.Optional(ATTR_TRACKNAME): cv.string,
                vol.Optional(ATTR_TRACK_NUMBER): cv.positive_int,
                vol.Optional(ATTR_DURATION): cv.positive_int,
                vol.Optional(ATTR_POSITION): cv.positive_int,
                vol.Optional(ATTR_VOLUME): cv.positive_float
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
)

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
        self._attr_unique_id = "unique_id"

        self._attr_media_album_artist = ""
        self._track_artist = ""
        self._track_album_name = ""
        self._track_name = ""
        self._album_art = None
        self._volume = 0.0
        self._attr_state = MediaPlayerState.PAUSED
        self._attr_media_content_type = MediaType.MUSIC
        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        def update_availability(payload: str) -> None:
            """Update device availability"""
            self._attr_available = payload == "online"
            self.schedule_update_ha_state(True)

        def update_state(payload: str) -> None:
            """Update device state"""
            try:
                data = STATUS_PAYLOAD(payload)
            except vol.MultipleInvalid as error:
                _LOGGER.debug("Skipping update because of malformatted data: %s", error)
                return

            self._track_artist = data.get(ATTR_ARTIST)
            self._attr_media_album_artist = data.get(ATTR_ARTIST)
            self._track_album_name = data.get(ATTR_ALBUM)
            self._track_name = data.get(ATTR_TRACKNAME)
            self._attr_media_track = data.get(ATTR_TRACK_NUMBER)
            self._attr_media_duration = data.get(ATTR_DURATION)
            self._attr_media_position = data.get(ATTR_POSITION)
            self._volume = data.get(ATTR_VOLUME)
            self._attr_is_volume_muted = self._volume == 0
            self._attr_available = True
            self._attr_state = MediaPlayerState.PLAYING

            self.schedule_update_ha_state(True)

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
                        case 'state':
                            update_state(data)

            except vol.MultipleInvalid as error:
                _LOGGER.debug("Skipping update because of malformatted data: %s", error)
                return

        await mqtt.async_subscribe(self.hass, SUBSCRIBE_TOPIC, message_received, 1)

    # Exposed properties
    @property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        return MediaPlayerDeviceClass.RECEIVER

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return SUPPORT_FEATURES

    # Commands
    async def async_media_play(self) -> None:
        """Send play command."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/play")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/pause")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/stop")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/previous")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/next")

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/seek", position)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/repeat")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/volume", volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/volume", 0)


def _parse_topic(topic: str) -> dict[str, Any]:
    """Parse the mqtt topic string"""
    parts = topic.split("/")
    if len(parts) < 3:
        return

    device= parts[1]
    command = parts[2]
    device_id = _slugify_upper(device)

    return {ATTR_DEVICE_ID: device_id, ATTR_COMMAND: command}
