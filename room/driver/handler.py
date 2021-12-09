import digi
import digi.on as on

import digi.util as util
from digi.util import deep_get, deep_set, mount_size

"""
Room:
- Adjust lamp power and brightness based on pre-defined modes;
- Adjust lamp brightness based on the (aggregate) brightness; 
    - brightness is "divided" uniformly across lamps
- When scene is mounted, keep track of what objects are in the room.

Control:
- Room's modes, each with a preset lamp power and brightness
- Room's brightness. Only effective when the lamps' powers are on 
  but otherwise overwrites the mode's preset brightness value.

Automation:
- In adaptive mode, if a scene is mounted then automatically
  turn on and off lamps based on human presence.
- TBD meta.turn_off_delay  

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
    "adaptive": {
        # turn on lamps upon human presence
        # default brightness set to max(brightness.min, last_value)
        "lamps": {
            "brightness": {
                "min": 0.5,
            },
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

        room_brightness = min(room_brightness, 1)
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
    scenes = mounts.get(gvr_scene, {})
    if len(scenes) < 1:
        deep_set(room, f"obs.objects", None, create=True)
        return

    for _, s in scenes.items():
        objects = deep_get(s, "spec.data.output.objects", None)
        deep_set(room, f"obs.objects", objects, create=True)


@on.mount
@on.control("mode", prio=0)
def do_mode(parent, mounts):
    room = parent

    mode = deep_get(room, "control.mode.intent")
    if mode is None:
        return

    power_convert = lamp_converters[gvr_lamp]["power"]["to"]
    brightness_convert = lamp_converters[gvr_lamp]["brightness"]["to"]
    lamp_config, room_brightness = mode_config[mode]["lamps"], list()

    objects = deep_get(room, "obs.objects", {})
    human_presence = None if objects is None \
        else any(o.get("class", None) == "human" for o in objects)
    deep_set(room, f"obs.human_presence", human_presence, create=True)

    # iterate over individual lamp
    for _, lamp in mounts.get(gvr_lamp, {}).items():
        power_intent = None
        if "power" in lamp_config:
            power_intent = lamp_config["power"]
        if mode == "adaptive":
            if human_presence:
                power_intent = power_convert("on")
            else:
                power_intent = power_convert("off")
        if power_intent is not None:
            deep_set(lamp, "spec.control.power.intent",
                     power_convert(power_intent))

        # add brightness
        power = deep_get(lamp, "spec.control.power.intent", "")
        brightness = deep_get(lamp, "spec.control.brightness.intent", 0)

        if power_convert(power) == "on":
            room_brightness.append(brightness_convert(brightness))

    if "brightness" in lamp_config:
        _max = lamp_config["brightness"].get("max", 1)
        _min = lamp_config["brightness"].get("min", 0)

        # reset the lamps' brightness only when they
        # don't fit the mode
        if not (_min <= sum(room_brightness) <= _max) and len(room_brightness) > 0:
            _bright_intent = deep_get(room, "control.brightness.intent")

            if _min <= _bright_intent <= _max:
                _bright_div = round(_bright_intent / len(room_brightness), 2)
            elif _bright_intent < _min:
                _bright_div = round(_min / len(room_brightness), 2)
            else:
                _bright_div = round(_max / len(room_brightness), 2)
            _set_bright(mounts, _bright_div)


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

def load():
    model = digi.rc.view()

    record = {
        "brightness": util.deep_get(model, "control.brightness.status"),
    }

    mounts = model.get("mount", {})
    lamps = mounts.get(gvr_lamp, None)
    if lamps is not None:
        record.update({"num_lamp": len(lamps)})

    objects = util.deep_get(model, f"obs.objects", None)
    if objects is not None:
        num_human, humans = 0, list()
        for o in objects:
            if "human" in o:
                num_human += 1
                humans.append(o["human"].get("name", None))
        record.update({"num_human": num_human, "human": humans})

    digi.pool.load([record])


loader = util.Loader(load_fn=load)


@on.meta
def do_meta(meta):
    i = meta.get("load_interval", -1)
    if i < 0:
        digi.logger.info("Stop loader")
        loader.stop()
    else:
        loader.reset(i)
        loader.start()


if __name__ == '__main__':
    digi.run()
