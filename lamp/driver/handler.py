"""Room scene."""
# event generation
@dbox.loop(cond=dbox.managed)
def event():
    presence = random.choice([True, False])
    dbox.model.patch(
        {"obs": {"human_presence": presence}})

# simulation
@dbox.on.model
def sim_occupancy(model, atts):
    presence = dbox.util.get(
    	model, "obs.human_presence", False)
    sensors = atts.get("occupancy", {})
    for name, model_sensor in sensors.items():
        dbox.util.update(model_sensor,
                         "obs.triggered", presence)


@dbox.loop(cond=dbox.managed)
def gen_event():
    motion = random.choice([True, False])
    dbox.model.update({{"obs": {"triggered": motion}}})


# handlers for simulation
@dbox.on.model
def sim(obs):
    dbox.broker.publish(obs)
