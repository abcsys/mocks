import digi
import digi.on as on


@on.control("power")
def h0(p):
    if "intent" in p:
        p["status"] = p["intent"]


@on.control("brightness")
def h1(b):
    if "intent" in b:
        b["status"] = b["intent"]


if __name__ == '__main__':
    digi.run()
