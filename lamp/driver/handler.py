import digi
import digi.on as on
import digi.util as util


@on.control("power")
def do_power(p):
    if "intent" in p:
        p["status"] = p["intent"]


@on.control
def do_brightness(sv):
    p, b = sv.get("power", {}), sv.get("brightness", {})
    if "intent" in b:
        if p.get("status", "off") == "on":
            b["status"] = b["intent"]
        else:
            b["status"] = 0


def load():
    model = digi.rc.view()
    digi.pool.load(
        [{
            "power": util.deep_get(model, "control.power.status"),
            "brightness": util.deep_get(model, "control.brightness.status"),
        }]
    )


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
