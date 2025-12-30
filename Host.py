from statistics import mode
from simulator.SimulatedEntity import SimulatedEntity
from enum import Enum

class ReliabilityMode(Enum):
    NO_RELIABILITY = 0
    ACKNOWLEDGES = 1
    ACKNOWLEDGES_WITH_RETRANSMISSION = 2
    PIPELINING_FIXED_WINDOW = 3
    PIPELINING_DYNAMIC_WINDOW = 4


class Host(SimulatedEntity):
    
    def __init__(self, sim, name, mode=ReliabilityMode.NO_RELIABILITY):
        super().__init__(sim, logger_name='Hosts')
        self._name = name
        self._nic = None
        self._mode = mode
        
    def add_nic(self, nic):
        assert nic.host() == None
        nic.set_host(self)
        self._nic = nic
    
    def receive(self, nic, pkt):
        assert nic == self._nic
        self.info(f'received {pkt} on {nic}')
    
    def send(self, pkts):
        if self._mode == ReliabilityMode.NO_RELIABILITY:
            for pkt in pkts:
                self.info(f'sends {pkt} on {self._nic}')
                self._nic.send(pkt)
        else:
            raise NotImplementedError('This reliability mode is not yet implemented.')
        
    def __repr__(self):
        return f'Host({self._name})'

