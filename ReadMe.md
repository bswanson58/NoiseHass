# NoiseHass

An integration for Home Assistant to support a media player entity using MQTT as the communication mechanism to the player.

---

The integration communicates through a series of MQTT topics:

noisemusicsystem/{DEVICE ID}/availability

noisemusicsystem/{DEVICE ID}/status

noisemusicsystem/{DEVICE ID}/command



The availability topic has a payload of either 'online' or 'offline' in raw format.

The status and command topics have payload in JSON format:

{    

    "artist": "Artist Name",

    "album": "Album Title",

    "trackname": "Track Title",

    "tracknumber": 7,

    "duration": 120,

    "position": 60,

    "positionat":"Wed, 18 Oct 2023 10:41:58 GMT",

    "volume": 75,

    "muted": false,

    "playstate": "playing"

}

'Duration' and 'position' are expressed in seconds.

'PositionAt' is the time, expressed in RFC 1123 format, that the position value was recorded.

'Volume' is expressed as a range from 0 to 100.

'PlayState' is 'playing' or anything else that is interpreted as not playing.



The command payload is:

{

    "command": "play",

    "parameter": ""

}



Valid commands are: 'next', 'mute', 'pause', 'play', 'repeat', 'seek', 'stop', 'previous', 'volume'

Seek has a parameter that indicates the position in seconds to seek to.

Volume has a parameter from 0 to 100 for the desired volume level.

Mute has a parameter of 'true' or 'false'.

Repeat will repeat the currently playing track.



The Home Assistant configuration is:

media_player:

  - platform: noise_music_system

    device_id: "NoiseBox"

    name: "Noise Music System"



The integration files should be placed under: config/custom_components/noise_music_system

The device ID should be configured to the unique value that the player will use to transmit topics.
