import digi
import digi.on as on
import digi.util as util

from digi import dbox
import random


@on.mount
def do_manage(mounts):
    dbox.manage(mounts)


# event
@dbox.loop
def event():
    presence = random.choice([True, False])
    digi.model.patch({
        "obs": {"human_presence": presence}
    })


# sim
@on.obs
def do_obs(sv, mounts):
    ocs = mounts.get(util.gvr_of("occupancy"), {})
    for _, oc in ocs.items():
        util.update(oc, "spec.obs.motion_detected",
                    sv.get("human_presence", False))


# log
@on.obs
def log(sv):
    digi.pool.load([sv])


if __name__ == '__main__':
    digi.run()
