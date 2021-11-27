import digi
import digi.on as on

import digi.util as util
from digi.util import put, deep_get, deep_set, mount_size

"""
Room digivice:
1. Adjust lamp power and brightness based on pre-defined modes (default priority 0);
2. Adjust lamp brightness based on the (aggregate) brightness (default priority 1); 
    - brightness is "divided" uniformly across lamps
3. Intent propagation is implemented for the universal lamp's power only.

Mounts:
-  mock.digi.dev/v1/lamps

"""

ul_gvr = "mock.digi.dev/v1/lamps"

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
    "sleep": {
        "lamps": {
            "power": "off",
        }
    },
    "idle": {
        "lamps": {
            "brightness": {
                "max": 0.3,
                "min": 0.0,
            }
        }
    }
}

lamp_converters = {
    ul_gvr: {
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

# intent reconciliation
@on.mount
def h(parent, bp):
    room = parent

    for _, child_path, old, new in bp:
        typ, attr = util.typ_attr_from_child_path(child_path)

        if typ == ul_gvr and attr == "power":
            put(path="control.power.intent",
                src=new, target=room)


# status
@on.control
@on.mount
def default(sv, mounts):
    # if no mounted devices, set the
    # status to intent
    if util.mount_size(mounts) == 0:
        for _, v in sv.items():
            if "intent" in v:
                v["status"] = v["intent"]


@on.control
@on.mount
def h(parent, mounts):
    room, devices = parent, mounts
    mode = deep_get(room, "control.mode.intent")
    _config = mode_config[mode]["lamps"]

    # handle mode and brightness
    matched = True
    _bright = 0

    for lt in [ul_gvr]:
        _pc = lamp_converters[lt]["power"]["from"]
        _bc = lamp_converters[lt]["brightness"]["from"]

        # iterate over individual lamp
        for n, _l in devices.get(lt, {}).items():
            if "spec" not in _l:
                continue
            _l = _l["spec"]

            _p = deep_get(_l, "control.power.status", None)
            _b = deep_get(_l, "control.brightness.status", 0)

            # check power
            if "power" in _config and _config["power"] != _pc(_p):
                matched = False

            # add brightness
            if _pc(_p) == "on":
                _bright += _bc(_b)

    deep_set(room, f"control.brightness.status", _bright)

    if "brightness" in _config:
        _max = _config["brightness"].get("max", 1)
        _min = _config["brightness"].get("min", 0)
        if not (_min <= _bright <= _max):
            matched = False

    # other devices
    ...

    deep_set(room, f"control.mode.status", mode if matched else "undef")


# intent
@on.mount
@on.control("mode", prio=0)
def do_mode_lamps(parent, mounts):
    room, devices = parent, mounts

    mode = deep_get(room, "control.mode.intent")
    if mode is None:
        return

    _config = mode_config[mode]["lamps"]

    _bright = list()
    for lt in [ul_gvr]:
        _pc = lamp_converters[lt]["power"]["to"]
        _bc = lamp_converters[lt]["brightness"]["to"]

        # iterate over individual lamp
        for n, _l in devices.get(lt, {}).items():

            _p = deep_get(_l, "spec.control.power.intent")
            _b = deep_get(_l, "spec.control.brightness.intent", 0)

            # set power
            if "power" in _config:
                deep_set(_l, "spec.control.power.intent",
                         _pc(_config["power"]))

            # add brightness
            if _pc(_p) == "on":
                _bright.append(_bc(_b))

    if "brightness" in _config:
        _max = _config["brightness"].get("max", 1)
        _min = _config["brightness"].get("min", 0)

        # reset the lamps' brightness only when they
        # don't fit the mode
        if not (_min <= sum(_bright) <= _max) and len(_bright) > 0:
            _bright = deep_get(room, "control.brightness.intent")
            if _min <= _bright <= _max:
                _bright_div = _bright
            else:
                _bright_div = (_max + _min) / 2 / len(_bright)
            _set_bright(devices, _bright_div)


@on.mount
@on.control("brightness", prio=0)
def do_bright(parent, mounts):
    room, devices = parent, mounts

    bright = deep_get(room, "control.brightness.intent")
    if bright is None:
        return

    num_active_lamp = \
        mount_size(mounts, {ul_gvr}, has_spec=True,
                   cond=lambda m: deep_get(m, "spec.control.power.status") == "on")

    if num_active_lamp < 1:
        return

    bright_div = bright / num_active_lamp
    _set_bright(devices, bright_div)


def _set_bright(ds, b):
    for lt in [ul_gvr]:
        _lc = lamp_converters[lt]["brightness"]["to"]

        for _, _l in ds.get(lt, {}).items():
            deep_set(_l, "spec.control.brightness.intent",
                     _lc(b))


if __name__ == '__main__':
    digi.run()
