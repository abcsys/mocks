import digi
from digi import on, dbox


@dbox.loop
def event():
    motion = dbox.random.choice([True, False])
    digi.logger.info(f"DEBUG {motion}")
    digi.model.patch("obs.motion_detected", motion)


@on.obs("motion_detected")
def do_obs(sv):
    digi.pool.load([{"motion": sv}])


if __name__ == '__main__':
    digi.run()
