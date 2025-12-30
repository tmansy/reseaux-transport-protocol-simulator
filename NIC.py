
from simulator.SimulatedEntity import SimulatedEntity
from simulator.Event import Event

from random import random

class NIC(SimulatedEntity):
    
    def __init__(self, sim, name, rate, queue_size=0):
        super().__init__(sim, 'NIC')
        self._name = name
        self._rate = rate
        self._queue = []
        self._queue_size = queue_size # in number of packets; 0 = infinite
        self._transmitting = False
        self.__link = None
        self.__host = None
        
    def get_rate(self):
        return self._rate
    
    def queue_depth(self):
        return len(self._queue)
        
    def host(self):
        return self.__host
    
    def set_host(self, host):
        self.__host = host
        
    def attach(self, link):
        self.__link = link
        link.attach(self)
        
    def delay_tr(self, packet_size):
        return packet_size * 8 / self._rate
    
    def __transmitted(self, pkt):
        self.debug(f'end of transmission {pkt}')
        if self.queue_depth() > 0:
            pkt = self._queue[0]
            self._queue = self._queue[1:]
            self.__transmit(pkt)
        else:
            self._transmitting = False
            
    def __received(self, pkt):
        self.debug(f'received {pkt}')
        self.__host.receive(self, pkt)
            
    def __transmit(self, pkt):
        self._transmitting = True
        self.debug(f'transmitting {pkt}, queue depth = {self.queue_depth()}')
        self._sim.add_event( Event(pkt, self.__transmitted), self.delay_tr(pkt.size) )
        if random() < self.__link.lost_prob:
            self.info(f'packet {pkt} lost on link {self.__link}')
            return
        self._sim.add_event( Event(pkt, self.__link.other(self).__received), self.delay_tr(pkt.size) + self.__link.delay_pr() ) # schedule reception at other end only if the packet is not lost
        
    def send(self, pkt):
        if self._transmitting:
            if self._queue_size == 0 or self.queue_depth() + 1 < self._queue_size:
                self.debug(f'enqueue {pkt}')
                self._queue.append(pkt)
            else:
                self.info(f'dropped {self.__host._name}:{self._name}')
                self.debug(f'drop {pkt}')
        else:
            self.__transmit(pkt)
            
    def __repr__(self):
        return f'NIC({self.__host._name}:{self._name})'
            
            