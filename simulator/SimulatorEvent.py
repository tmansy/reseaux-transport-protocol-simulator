from dataclasses import dataclass, field
from typing import Any

# Class to handle simulator events, a couple (time, event)
# where time is a float that represents the occurrence time
# and event is the event itself
#
# The time is used as priority for the queue of events.
# The event must support a 'run' instance method without argument.
#
# Note: implemented as a triplet with the additional second component
#       being a unique event number; allows for total ordering including
#       over events that have the same occurrence time
@dataclass(order=True)
class SimulatorEvent:
    time : float
    num  : int
    event: Any=field(compare=False)