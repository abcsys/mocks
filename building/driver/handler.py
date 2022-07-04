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
    num_human = random.randint(0, 2)
    digi.model.patch({
        "obs": {"num_human": num_human}
    })


# sim
@on.obs
def do_obs(sv, mounts):
    rooms = mounts.get(util.gvr_of("room"), {})
    names, num_human = list(rooms.keys()), sv.get("num_human", 0)
    if len(names) < 1:
        return
    picked = set(random.choices(names, k=num_human))
    for name, room in rooms.items():
        util.update(room, "spec.obs.human_presence", name in picked)


# log
@on.obs
def log(sv):
    digi.pool.load([sv])


if __name__ == '__main__':
    digi.run()
