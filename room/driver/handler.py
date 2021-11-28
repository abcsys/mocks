import digi
import digi.on as on

import digi.util as util
from digi.util import put, deep_get, deep_set, mount_size

"""
Room:
- Adjust lamp power and brightness based on pre-defined modes;
- Adjust lamp brightness based on the (aggregate) brightness; 
    - brightness is "divided" uniformly across lamps
- When scene is mounted, keep track of what objects are in the room.

Mounts:
-  mock.digi.dev/v1/lamps
-  mock.digi.dev/v1/scenes

"""

gvr_lamp = "mock.digi.dev/v1/lamps"
gvr_scene = "mock.digi.dev/v1/scenes"

mode_config = {
    "work": {
        "lamps": {
            "power": "on",
            "brightness": {
                "max": 1,
                "min": 0.7,
            },
            "ambiance_color": "white",
        }
    },
    "idle": {
        "lamps": {
            "brightness": {
                "max": 0.3,
                "min": 0.0,
            }
        }
    },
    "sleep": {
        "lamps": {
            "power": "off",
        }
    },
}

lamp_converters = {
    gvr_lamp: {
        "power": {
            "from": lambda x: x,
            "to": lambda x: x,
        },
        "brightness": {
            "from": lambda x: x,
            "to": lambda x: x,
        }
    },
}


@on.control
@on.mount
def do_room_status(parent, mounts):
    room, devices = parent, mounts
    # if no mounted devices, set the
    # status to intent
    if util.mount_size(mounts) == 0:
        for _, v in room.items():
            if "intent" in v:
                v["status"] = v["intent"]
        return

    def set_room_mode_brightness():
        room_brightness, matched = 0, True

        mode = deep_get(room, "control.mode.intent")
        lamp_config = mode_config[mode]["lamps"]

        power_convert = lamp_converters[gvr_lamp]["power"]["from"]
        brightness_convert = lamp_converters[gvr_lamp]["brightness"]["from"]

        # iterate over individual lamp
        for n, lamp in devices.get(gvr_lamp, {}).items():
            if "spec" not in lamp:
                continue

            lamp_spec = lamp["spec"]
            lamp_power = deep_get(lamp_spec, "control.power.status", None)
            lamp_brightness = deep_get(lamp_spec, "control.brightness.status", 0)

            if "power" in lamp_config and lamp_config["power"] != power_convert(lamp_power):
                matched = False

            if power_convert(lamp_power) == "on":
                room_brightness += brightness_convert(lamp_brightness)

        deep_set(room, f"control.brightness.status", room_brightness)

        if "brightness" in lamp_config:
            _max = lamp_config["brightness"].get("max", 1)
            _min = lamp_config["brightness"].get("min", 0)
            if not (_min <= room_brightness <= _max):
                matched = False

        deep_set(room, f"control.mode.status", mode if matched else "undef")

    # other devices
    # ...

    # TBD use class for room
    set_room_mode_brightness()


@on.mount
@on.control
def do_obs(parent, mounts):
    room = parent
    # XXX handle at most one scene only
    for _, s in mounts.get(gvr_scene, {}).items():
        objects = deep_get(s, "spec.data.output.objects", None)
        deep_set(room, f"obs.objects", objects)


@on.mount
@on.control("mode", prio=0)
def do_mode(parent, mounts):
    room, devices = parent, mounts

    mode = deep_get(room, "control.mode.intent")
    if mode is None:
        return

    _pc = lamp_converters[gvr_lamp]["power"]["to"]
    _bc = lamp_converters[gvr_lamp]["brightness"]["to"]
    _lamp_config, _bright = mode_config[mode]["lamps"], list()

    # iterate over individual lamp
    for n, _l in devices.get(gvr_lamp, {}).items():

        _p = deep_get(_l, "spec.control.power.intent")
        _b = deep_get(_l, "spec.control.brightness.intent", 0)

        # set power
        if "power" in _lamp_config:
            deep_set(_l, "spec.control.power.intent",
                     _pc(_lamp_config["power"]))

        # add brightness
        if _pc(_p) == "on":
            _bright.append(_bc(_b))

    if "brightness" in _lamp_config:
        _max = _lamp_config["brightness"].get("max", 1)
        _min = _lamp_config["brightness"].get("min", 0)

        # reset the lamps' brightness only when they
        # don't fit the mode
        if not (_min <= sum(_bright) <= _max) and len(_bright) > 0:
            _bright_intent = deep_get(room, "control.brightness.intent")
            if _min <= _bright_intent <= _max:
                _bright_div = _bright_intent / len(_bright)
            elif _bright_intent < _min:
                _bright_div = _min / len(_bright)
            else:
                _bright_div = _max / len(_bright)
            _set_bright(devices, _bright_div)


@on.mount
@on.control("brightness", prio=0)
def do_brightness(parent, mounts):
    room, devices = parent, mounts

    brightness = deep_get(room, "control.brightness.intent")
    if brightness is None:
        return

    num_active_lamp = \
        mount_size(mounts, {gvr_lamp}, has_spec=True,
                   cond=lambda m: deep_get(m, "spec.control.power.status") == "on")

    if num_active_lamp < 1:
        return

    brightness_div = brightness / num_active_lamp
    _set_bright(devices, brightness_div)


def _set_bright(ds, b):
    _lc = lamp_converters[gvr_lamp]["brightness"]["to"]

    for _, _l in ds.get(gvr_lamp, {}).items():
        deep_set(_l, "spec.control.brightness.intent",
                 _lc(b))


if __name__ == '__main__':
    digi.run()
