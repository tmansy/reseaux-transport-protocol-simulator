from simulator.SimulatedEntity import SimulatedEntity

class Router(SimulatedEntity):
    
    def __init__(self, sim, name):
        super().__init__(sim, logger_name='Routers')
        self._name = name
        self._nics = []
        
    def add_nic(self, nic):
        assert nic.host() == None
        nic.set_host(self)
        self._nics.append(nic)
        
    def receive(self, nic, pkt):
        # Super router : always send through the other NIC
        assert len(self._nics) == 2
        assert nic in self._nics
        other_nic = self._nics[1] if self._nics[0] == nic else self._nics[0]
        self.info(f'received {pkt} on {nic}, forwarded on {other_nic}')
        other_nic.send(pkt)
        self.debug(f'Queue depth on {other_nic} = {other_nic.queue_depth()}')
        
    def __repr__(self):
        return f'Router({self._name})'