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
from homeassistant.components.media_player import ( PLATFORM_SCHEMA, MediaPlayerEntity, MediaPlayerDeviceClass, RepeatMode )
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_COMMAND,
    ATTR_ID,
    CONF_DEVICE_ID,
    CONF_NAME,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
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
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_VOLUME_SET
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY
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
        self._attr_available = False
        self._subscribe_topic = "noisemusicsystem/#"

        self._volume = 70
        self._track_name = "Tumbling Dice"
        self._attr_media_album_artist = "The Rolling Stones"
        self._track_artist = "The Rolling Stones"
        self._track_album_name = "Sticky Fingers"
        self._state = STATE_PLAYING
        self._album_art = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        def update_availability(payload: str) -> None:
            """Update device availability"""
            self._attr_available = payload == "online"
            self.schedule_update_ha_state(True)

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

    # Exposed properties
    @property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        return MediaPlayerDeviceClass.RECEIVER

    @property
    def name(self) -> str:
        return self._name

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def state(self) -> str:
        return self._state

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return SUPPORT_FEATURES

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self._attr_media_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self._attr_media_position

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        return self._attr_media_position_updated_at

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._track_name

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._track_artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._track_album_name

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self._attr_media_album_artist

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self._attr_media_track

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        return self._attr_source

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._attr_is_volume_muted

    # Commands
    async def async_media_play(self) -> None:
        """Send play command."""
        await self.hass.async_add_executor_job(self.media_play)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.hass.async_add_executor_job(self.media_pause)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.hass.async_add_executor_job(self.media_stop)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.hass.async_add_executor_job(self.media_previous_track)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.hass.async_add_executor_job(self.media_next_track)

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.hass.async_add_executor_job(self.media_seek, position)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.hass.async_add_executor_job(self.set_repeat, repeat)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await mqtt.async_publish(self.hass, "noisemusicsystem/SaltMine/command/volume", volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.hass.async_add_executor_job(self.mute_volume, mute)


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
