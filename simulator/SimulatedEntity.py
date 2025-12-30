import logging

class SimulatedEntity:
    
    def __init__(self, sim, logger_name=None):
        self._sim = sim
        if logger_name != None:
            self._logger = logging.getLogger(logger_name)
        else:
            self._logger = logging.getLogger()
        
    def _now(self):
        return self._sim.now()
    
    def debug(self, msg):
        self._logger.debug(f'@{self._now():.6f}, {self} {msg}')
        
    def info(self, msg):
        self._logger.info(f'@{self._now():.6f}, {self} {msg}')