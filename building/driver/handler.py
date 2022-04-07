import digi
from digi import on, util

room_gvr = "mock.digi.dev/v1/rooms"


class Building:
    def __init__(self):
        self.old_rooms, self.rooms = dict(), dict()

    def update(self):
        model = digi.model.get()
        self.old_rooms = self.rooms
        self.rooms = util.get(model, f"mount.'{room_gvr}'", {})


building = Building()


# @on.pool(in_flow="")
# def gen_occupancy(records):
#     digi.logger.info(f"Records: {records}")
#     if len(records) == 0:
#         return


@on.mount
def update_occupancy_flow(model):
    building.update()
    num_room = len(building.rooms)
    if num_room == len(building.old_rooms):
        return

    if num_room == 0:
        digi.util.update(model, "egress.occupancy.pause", True)
    else:
        digi.util.update(model, "egress.occupancy.pause", False)
        digi.util.update(model, "egress.occupancy.flow",
                         f"occupancy > 0.2 | count := count() | "
                         f"occupancy:=cast(count, <float64>)/{len(building.rooms)} |"
                         f"cut occupancy")


if __name__ == '__main__':
    digi.run()
