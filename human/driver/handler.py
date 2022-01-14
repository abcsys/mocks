import json
import os

import digi
import digi.util as util

import numpy as np
import yaml

"""
Update the room model directly, without going through the mounter.
"""

gvr_room = "smarthome.mock.digi.dev/v1/rooms"
_dir = os.path.dirname(os.path.abspath(__file__))
_behavior_config = os.path.join(_dir, "behavior.yaml")


# Human model
class Human:
    def __init__(self, name=digi.name, seed=42):
        with open(_behavior_config, "r") as f:
            self.behavior_config = yaml.load(f, Loader=yaml.FullLoader)
        self.name = name
        self.cur_gen = 0
        self.cur_time = 0
        self.stayed = False
        # TBD load initial room from model
        self.cur_room = "bedroom"
        self.cur_activity = "sleep"
        self.last_room = None
        self.max_time = 48
        # TBD load seed from model
        # np.random.seed(seed)
        self.log()

    def __str__(self):
        return json.dumps({
            "name": self.name,
            "time": self.cur_time,
            "phase": self.phase_of_day(),
            "activity": self.cur_activity,
            "room": self.cur_room,
            "last_room": self.last_room,
        })

    def reset(self):
        self.cur_time = 0
        self.cur_room = "bedroom"
        self.cur_activity = "sleep"
        self.last_room = None
        self.stayed = False

    def phase_of_day(self):
        ratio = self.cur_time / self.max_time
        if ratio < 0.25:  # 6 - 12
            return "morning"
        elif ratio < 0.5:  # 12 - 18
            return "afternoon"
        elif ratio < 0.625:  # 18 - 21
            return "evening"
        else:
            return "night"

    def _transition(self, src, phase):
        """Return the destination given source and phase of day."""
        dests, probs = list(), list()
        for dest, config in self.behavior_config[src] \
                ["transition"][phase].items():
            dests.append(dest)
            probs.append(config["p"])
        return np.random.choice(dests, 1, p=probs)[0]

    def _activity(self, src):
        """Return the activity."""
        actvs, probs = list(), list()
        for name, config in self.behavior_config[src] \
                ["activity"].items():
            actvs.append(name)
            probs.append(config["p"])
        return np.random.choice(actvs, 1, p=probs)[0]

    def step(self):
        phase = self.phase_of_day()
        next_room = self._transition(self.cur_room, phase)
        if next_room != "stay":
            self.last_room = self.cur_room
            self.cur_room = next_room
            self.stayed = False
        else:
            self.stayed = True

        self.cur_activity = self._activity(self.cur_room)
        self.cur_time = (self.cur_time + 1) % self.max_time
        self.log()

    def update_room(self, rooms):
        patches = list()
        # iterate over rooms
        for room_nsn, model in rooms.items():
            room_name = util.simple_name(room_nsn)

            # update human presence
            patch = dict()
            util.update(patch, "spec.obs.human_presence",
                        room_name == self.cur_room, create=True)

            # update room obs.objects
            room_objects = util.get(model, "spec.obs.objects", [])
            new_room_objects = list()

            for o in room_objects:
                if o["class"] == "human" and o["name"] == self.name:
                    continue
                new_room_objects.append(o)

            if room_name == self.cur_room:
                new_room_objects.append({
                    "class": "human",
                    "name": self.name,
                    "activity": self.cur_activity
                })
            util.update(patch,
                        "spec.obs.objects",
                        new_room_objects,
                        create=True)

            room_brightness = util.get(model,
                                       "spec.control.brightness.status",
                                       -1)

            # update brightness of current room
            if room_name == self.cur_room:
                desired_brightness = util.get(self.behavior_config,
                                              f"{room_name}.activity."
                                              f"{self.cur_activity}"
                                              f".brightness")
                min_val = float(desired_brightness.get("min", 0.0))
                max_val = float(desired_brightness.get("max", 1.0))

                # if the room's brightness already fit the range,
                # don't update the brightness, otherwise set the
                # brightness to the mean
                if not (min_val < room_brightness < max_val):
                    mean_brightness = np.mean([min_val, max_val])
                    mean_brightness = round(float(mean_brightness), 1)

                    # update children directly
                    util.update(patch,
                                "spec.control.brightness.intent",
                                mean_brightness,
                                create=True)
            # if no one is in the room, turn off the lamps
            # to save energy except for the last room stayed,
            # to give an opportunity for automation
            elif room_name != self.last_room or self.stayed:
                # TBD: allow a low range to see any emergent behavior
                util.update(patch,
                            "spec.control.brightness.intent",
                            0.0,
                            create=True)

            # prepare the patch
            g, v, r = util.parse_gvr(gvr_room)
            n, ns = util.parse_spaced_name(room_nsn)
            patch = ((g, v, r, n, ns), patch.get("spec", {}))

            # ensure the last room gets patched first
            # to mimic the leaving room
            if room_name == self.last_room:
                patches.insert(0, patch)
            else:
                patches.append(patch)

        for duri, patch in patches:
            util.patch_spec(*duri, patch)

    def log(self):
        digi.pool.load([
            {
                "cur_gen": self.cur_gen,
                "cur_time": self.cur_time,
                "cur_room": self.cur_room,
                "cur_phase": self.phase_of_day(),
                "activity": self.cur_activity,
            }
        ])


human = Human(name=digi.name)


@digi.on.control("cur_gen")
def do_gen(sv):
    cur_gen = util.get(sv, f"intent", 0)
    if cur_gen > human.cur_gen:
        human.reset()
    human.cur_gen = cur_gen
    util.update(sv, f"status", cur_gen)


@digi.on.control("cur_time")
def do_time(sv):
    cur_time = util.get(sv, f"intent", 0)
    util.update(sv, f"status", cur_time)


@digi.on.model
def do_step(pv):
    global human
    rooms = util.get(pv, f"mount.'{gvr_room}'", {})

    cur_time_intent = util.get(pv, f"control.cur_time.intent", human.max_time)
    if human.cur_time % human.max_time <= cur_time_intent:
        human.step()

    human.update_room(rooms)


if __name__ == '__main__':
    digi.run()
