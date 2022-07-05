import digi
import digi.on as on
import digi.util as util

from digi import dbox
dbox.init()


# event
@dbox.loop
def event():
    presence = dbox.random.choice([True, False])
    digi.model.patch("obs.human_presence", presence)


# sim
@on.obs
def do_obs(sv, mounts):
    ocs = mounts.get(util.gvr_of("occupancy"), {})
    for _, oc in ocs.items():
        util.update(oc, "spec.obs.motion_detected",
                    sv.get("human_presence", False))
    digi.pool.load([sv])


if __name__ == '__main__':
    digi.run()
