import digi
import digi.on as on
import digi.util as util


@on.control
def do_control(sv):
    p, b = sv.get("power", {}), sv.get("brightness", {})
    if "intent" in p:
        p["status"] = p["intent"]

    if "intent" in b:
        if p.get("status", "off") == "on":
            b["status"] = b["intent"]
        else:
            b["status"] = 0


def report():
    model = digi.rc.view()
    power, brightness = util.get(model, "control.power.status"), \
                        util.get(model, "control.brightness.status")
    wattage = util.get(model, "meta.wattage", -1)
    watt = 0 if power != "on" else wattage
    digi.pool.load(
        [{
            "power": power,
            "brightness": brightness,
            "watt": watt,
        }]
    )


loader = util.Loader(load_fn=report)


@on.meta
def do_meta(meta):
    i = meta.get("report_interval", -1)
    if i < 0:
        digi.logger.info("Stop loader")
        loader.stop()
    else:
        loader.reset(i)
        loader.start()


if __name__ == '__main__':
    digi.run()
