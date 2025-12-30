from enum import Enum

class PacketType(Enum):
    DATA = 'DATA'

class Packet:
    
    def __init__(self, sn, size, type=PacketType.DATA):
        self.size = size # in bytes
        self.type = type
        self.serial_number = sn
        
    def __repr__(self):
        return f'Packet({self.type} SN={self.serial_number}, {self.size} bytes)'