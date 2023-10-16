"""Platform for Noise Music System integration"""
from __future__ import annotations

import datetime as dt
from pprint import pformat
import voluptuous as vol
import logging
import json
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.json import json_loads

from homeassistant.components.media_player.const import MediaPlayerEntityFeature
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

_LOGGER = logging.getLogger("noisemusicsystem")

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string
})

SUPPORT_FEATURES = (
      MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

# MQTT strings for topics/properties
TOPIC_BASE = 'noisemusicsystem'
SUBSCRIBE_TOPIC = f'{TOPIC_BASE}/#'

ONLINE_STATUS = 'online'

ATTR_ARTIST = 'artist'
ATTR_ALBUM = 'album'
ATTR_TRACKNAME = 'trackname'
ATTR_TRACK_NUMBER = 'tracknumber'
ATTR_DURATION = 'duration'
ATTR_POSITION = 'position'
ATTR_POSITION_AT = 'positionat'
ATTR_VOLUME = 'volume'
ATTR_VOLUME_MUTED = 'muted'
ATTR_PLAY_STATE = 'playstate'

PLAY_STATE_PLAYING = 'playing'

# Topic strings
COMMAND_TOPIC = 'command'

COMMAND_NEXT_TRACK = 'next'
COMMAND_MUTE = 'mute'
COMMAND_PAUSE = 'pause'
COMMAND_PLAY = 'play'
COMMAND_REPEAT = 'repeat'
COMMAND_SEEK = 'seek'
COMMAND_STOP = 'stop'
COMMAND_PREVIOUS_TRACK = 'previous'
COMMAND_VOLUME = 'volume'

# The expected MQTT status structure
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
                vol.Optional(ATTR_POSITION_AT): cv.string,
                vol.Optional(ATTR_VOLUME): cv.positive_float,
                vol.Optional(ATTR_VOLUME_MUTED): cv.boolean,
                vol.Optional(ATTR_PLAY_STATE): cv.string
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
)

# The MQTT playload for transmitted commands
class command_payload:
    def __init__(self, command: str, parameter: str = '') -> None:
        self.command: str = command
        self.parameter: str = parameter


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

    device: PLATFORM_SCHEMA = {
        CONF_NAME: config[CONF_NAME],
        CONF_DEVICE_ID: config[CONF_DEVICE_ID]
    }

    async_add_entities([NoiseMusicSystem(device, hass)])


class NoiseMusicSystem(MediaPlayerEntity):
    def __init__(self, device, hass: HomeAssistant) -> None:
        _LOGGER.info(pformat(device))
        self._hass = hass
        self._name = device[CONF_NAME]
        self._device_name = device[CONF_DEVICE_ID]

        self._device_id = _slugify_upper(device[CONF_DEVICE_ID])
        self._attr_unique_id = device[CONF_DEVICE_ID]

        self._attr_media_album_artist = ""
        self._track_artist = ""
        self._track_album_name = ""
        self._track_name = ""
        self._album_art = None
        self._volume = 0.0
        self._attr_state = MediaPlayerState.PAUSED
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        def update_availability(payload: str) -> None:
            """Update device availability"""
            self._attr_available = payload == ONLINE_STATUS
            self.schedule_update_ha_state(False)

        def update_status(payload: str) -> None:
            """Update device state"""
            try:
                data = STATUS_PAYLOAD(payload)
            except vol.MultipleInvalid as error:
                _LOGGER.debug(f'Status update has malformatted data: {error}')
                return

            self._attr_available = True
            self._track_artist = data.get(ATTR_ARTIST)
            self._attr_media_album_artist = data.get(ATTR_ARTIST)
            self._track_album_name = data.get(ATTR_ALBUM)
            self._track_name = data.get(ATTR_TRACKNAME)
            self._attr_media_track = data.get(ATTR_TRACK_NUMBER)
            self._attr_media_duration = data.get(ATTR_DURATION)
            self._attr_media_position = data.get(ATTR_POSITION)
            self._volume = data.get(ATTR_VOLUME) / 100.0
            self._attr_is_volume_muted = data.get(ATTR_VOLUME_MUTED)
            self._attr_state = MediaPlayerState.PLAYING if data.get(ATTR_PLAY_STATE) == PLAY_STATE_PLAYING else MediaPlayerState.PAUSED
            if(len(data.get(ATTR_POSITION_AT))):
                self._attr_media_position_updated_at = dt.datetime.strptime(data.get(ATTR_POSITION_AT), '%a, %d %b %Y %H:%M:%S GMT') #RFC 1123 format

            self.schedule_update_ha_state(False)

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                topic_info = _parse_topic(msg.topic)

                if topic_info.get(CONF_DEVICE_ID) == self._device_id:
                    match topic_info.get(ATTR_COMMAND):
                        case 'availability':
                            update_availability(msg.payload)
                        case 'status':
                            update_status(msg.payload)

            except vol.MultipleInvalid as error:
                _LOGGER.debug(f'Received message has malformatted data: {error}')
                return

        await mqtt.async_subscribe(self.hass, SUBSCRIBE_TOPIC, message_received, 1)


    # Exposed properties
    @property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        return MediaPlayerDeviceClass.RECEIVER

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        return MediaType.MUSIC

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return SUPPORT_FEATURES


    @property
    def media_title(self) -> str:
        """Title of current playing media."""
        return self._track_name

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self._attr_media_track

    @property
    def media_artist(self) -> str:
        """Artist of current playing media, music track only."""
        return self._track_artist

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self._attr_media_album_artist

    @property
    def media_album_name(self) -> str:
        """Album name of current playing media, music track only."""
        return self._track_album_name

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
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._attr_is_volume_muted

    # Commands
    async def publish_command(self, command: str, parameter: str = '') -> None:
        """Publish a command"""
        payload = command_payload(command, parameter)
        command_topic = f"{TOPIC_BASE}/{self._device_name}/{COMMAND_TOPIC}"

        await mqtt.async_publish(self.hass, command_topic, json.dumps(vars(payload)))

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.publish_command(COMMAND_PLAY)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.publish_command(COMMAND_PAUSE)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.publish_command(COMMAND_STOP)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.publish_command(COMMAND_PREVIOUS_TRACK)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.publish_command(COMMAND_NEXT_TRACK)

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.publish_command(COMMAND_SEEK, position)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.publish_command(COMMAND_REPEAT)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.publish_command(COMMAND_VOLUME, volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.publish_command(COMMAND_MUTE, mute)


def _slugify_upper(string: str) -> str:
    """Return a slugified version of string, uppercased."""
    return slugify(string).upper()


def _parse_topic(topic: str) -> dict[str, Any]:
    """Parse the mqtt topic string"""
    parts = topic.split('/')
    if len(parts) < 3:
        return

    device= parts[1]
    command = parts[2]
    device_id = _slugify_upper(device)

    return {ATTR_DEVICE_ID: device_id, ATTR_COMMAND: command}
