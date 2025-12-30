import queue
import logging

from simulator.SimulatorEvent import SimulatorEvent

# Simplest Discrete Event Simulator
class Simulator:
    
    _en = 0
    
    def __init__(self):
        self.reset()
        self.__logger = logging.getLogger('simulator')
        
    def add_event(self, event, delta_t):
        self.__logger.debug(f'Simulator queueing event {event} in {delta_t} s')
        assert delta_t >= 0
        self.q.put( SimulatorEvent(self.__now + delta_t, Simulator._en, event) )
        Simulator._en += 1
        
    def run(self):
        self.__logger.debug(f'running...')
        while self.q.qsize() > 0:
            self.__logger.debug(f'{self.q.qsize()} remaining events in simulator.')
            e = self.q.get()
            self.__now = e.time
            self.__logger.debug(f'now = {self.__now}')
            e.event.run()
        self.__logger.debug('terminated.')
            
    def now(self):
        return self.__now
    
    def reset(self):
        self.__now = 0
        self.q = queue.PriorityQueue()
            
