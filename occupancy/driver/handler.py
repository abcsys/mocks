import digi
from digi import on
import random
from digi import dbox

@dbox.loop
def event():
    motion = random.choice([True, False])
    digi.model.patch({
        "obs": {
            "motion_detected": motion
        }
    })
    digi.pool.load([{"motion": motion}])


def make_event_interval(avg_t):
    def fn() -> int:
        min_, max_ = int(avg_t / 2), int(avg_t * 2)
        return random.randint(min_, max_)

    return fn



if __name__ == '__main__':
    digi.run()
