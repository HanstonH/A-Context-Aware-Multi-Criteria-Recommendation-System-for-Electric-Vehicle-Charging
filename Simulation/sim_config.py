"""Shared SUMO simulation timing (1-hour default run)."""



SIM_END_S = 3600  # 1 hour — stop spawning new vehicles

TRIP_END_S = 3600

TRIP_PERIOD_S = 20  # one EV every 20s → ~180 vehicles in 1 hour

MAX_DRAIN_AFTER_END_S = 0  # total simulation length = SIM_END_S



# Route generation — prefer downtown trips over map-edge arrivals

TRIP_FRINGE_FACTOR = 1  # 1 = normal; higher values bias start/end to network fringe

TRIP_MIN_DISTANCE_M = 800  # skip very short hops that often end at road dead-ends

