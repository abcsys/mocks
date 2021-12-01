import sys
import time
import threading
import random

import digi
import digi.on as on
import digi.util as util

"""
Mock scene generates random objects if a url is provided.
"""

DEFAULT_ENTER_PROB = 0.1
DEFAULT_LEAVE_PROB = 0.1
DEFAULT_CLASS = "human"

scene = None


class Scene(threading.Thread):
    def __init__(self, objects, refresh_interval=1):
        threading.Thread.__init__(self)

        self.cur_objects = dict()
        self.possible_objects = objects
        self.interval = refresh_interval
        self.name_to_class = {
            name: config.get("class", "human")
            for name, config in self.possible_objects.items()
        }

        self._stop_flag = threading.Event()

    def run(self):
        self.gen_scene()

    def stop(self):
        self._stop_flag.set()

    def gen_scene(self):
        while not self._stop_flag.is_set():
            util.check_gen_and_patch_spec(*digi.auri,
                                          spec={
                                              "data": {
                                                  "output": {
                                                      "objects": self.gen_objects()
                                                  }
                                              }
                                          },
                                          gen=sys.maxsize)
            time.sleep(self.interval)

    def gen_objects(self):
        # TBD gen objects from trace
        object_to_enter = dict()
        for name, config in self.possible_objects.items():
            if name in self.cur_objects:
                continue

            prob = config.get("enter_prob", DEFAULT_ENTER_PROB)

            if not happen(prob):
                continue

            object_to_enter[name] = {
                "location": {
                    "x1": random.randint(100, 1000),
                    "x2": random.randint(100, 1000),
                    "w": random.randint(0, 200),
                    "h": random.randint(0, 200),
                },
                "name": name if self.name_to_class[name] == "human" else "misc",
            }

        object_to_leave = list()
        for name, _ in self.cur_objects.items():
            config = self.possible_objects[name]
            prob = config.get("leave_prob", DEFAULT_ENTER_PROB)
            if happen(prob):
                object_to_leave.append(name)

        # merge
        for name in object_to_leave:
            del self.cur_objects[name]

        self.cur_objects.update(object_to_enter)

        return [{self.name_to_class[name]: loc}
                for name, loc in self.cur_objects.items()]


def happen(prob):
    return random.random() < prob


@on.attr("meta")
@on.data("input")
@on.attr("object_config")
def init(model):
    global scene
    if scene is not None:
        scene.stop()
    if util.deep_get(model, "meta.pause", False):
        return

    digi.logger.info("init scene")
    objects = util.deep_get(model, "meta.object_config", {})
    interval = util.deep_get(model, "meta.refresh_interval", 1)
    seed = util.deep_get(model, "meta.seed", 42)

    scene = Scene(objects, interval)
    random.seed(seed)
    scene.start()


if __name__ == '__main__':
    digi.run()
