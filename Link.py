# Link between two Network Interface Cards
class Link:
    
    def __init__(self, name, distance, speed, lost_prob=0):
        self._name = name
        self.distance = distance
        self.speed = speed
        self.lost_prob = lost_prob # probability of losing a packet
        self.__nics = []
        
    def delay_pr(self):
        return self.distance /self.speed
    
    def attach(self, nic):
        assert nic not in self.__nics, "NIC already attached"
        assert len(self.__nics) < 2, "link already attached to 2 NICs"
        if len(self.__nics) == 1:
            assert self.__nics[0].get_rate() == nic.get_rate(), "NIC speed mismatch"
        self.__nics.append( nic )
        
    def other(self, nic):
        assert len(self.__nics) == 2, "no other NIC attached"
        assert nic in self.__nics, "NIC not attached to link"
        if self.__nics[0] == nic:
            return self.__nics[1]
        else:
            return self.__nics[0]
        
    def __repr__(self):
        return f'Link({self._name})'