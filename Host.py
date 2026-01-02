from simulator.SimulatedEntity import SimulatedEntity
from simulator.Event import Event
from Packet import Packet, PacketType
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
        
        # For ACKNOWLEDGES et ACKNOWLEDGES_WITH_RETRANSMISSION
        self._packets_to_send = []
        self._waiting_for_ack = False
        self._expected_ack = None
        
        # For ACKNOWLEDGES_WITH_RETRANSMISSION
        self._timer_active = False
        self._current_packet = None
        self._timeout_delay = 0.1  # in sec
        
        # For PIPELINING
        self._window_size = 5
        self._send_base = 1
        self._next_seq_num = 1
        self._packets_sent = {}
        self._receive_buffer = {}
        self._next_expected_seq = 1
        
    def add_nic(self, nic):
        assert nic.host() == None
        nic.set_host(self)
        self._nic = nic
    
    def receive(self, nic, pkt):
        assert nic == self._nic
        self.info(f'received {pkt} on {nic}')
        
        if self._mode == ReliabilityMode.ACKNOWLEDGES:
            if pkt.type == PacketType.DATA:
                ack = Packet(sn=pkt.serial_number, size=pkt.size, type=PacketType.ACK)
                self.info(f'sending ACK for {pkt.serial_number}')
                self._nic.send(ack)
            elif pkt.type == PacketType.ACK:
                if self._waiting_for_ack and pkt.serial_number == self._expected_ack:
                    self.info(f'ACK {pkt.serial_number} received')
                    self._waiting_for_ack = False
                    self._send_next_packet()
        
        elif self._mode == ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION:
            if pkt.type == PacketType.DATA:
                ack = Packet(sn=pkt.serial_number, size=pkt.size, type=PacketType.ACK)
                self.info(f'sending ACK for {pkt.serial_number}')
                self._nic.send(ack)
            elif pkt.type == PacketType.ACK:
                if self._waiting_for_ack and pkt.serial_number == self._expected_ack:
                    self.info(f'ACK {pkt.serial_number} received, cancelling timer')
                    self._timer_active = False
                    self._waiting_for_ack = False
                    self._current_packet = None
                    self._send_next_packet()
        
        elif self._mode == ReliabilityMode.PIPELINING_FIXED_WINDOW:
            if pkt.type == PacketType.DATA:
                if pkt.serial_number == self._next_expected_seq:
                    self.info(f'received expected packet {pkt.serial_number}')
                    self._next_expected_seq += 1
                    
                    while self._next_expected_seq in self._receive_buffer:
                        self.info(f'delivering buffered packet {self._next_expected_seq}')
                        del self._receive_buffer[self._next_expected_seq]
                        self._next_expected_seq += 1
                    
                    ack = Packet(sn=self._next_expected_seq - 1, size=pkt.size, type=PacketType.ACK)
                    self.info(f'sending cumulative ACK {self._next_expected_seq - 1}')
                    self._nic.send(ack)
                
                elif pkt.serial_number > self._next_expected_seq:
                    self.info(f'packet {pkt.serial_number} out of order, buffering (expected {self._next_expected_seq})')
                    self._receive_buffer[pkt.serial_number] = pkt
                    
                    ack = Packet(sn=self._next_expected_seq - 1, size=pkt.size, type=PacketType.ACK)
                    self.info(f'sending cumulative ACK {self._next_expected_seq - 1}')
                    self._nic.send(ack)
                else:
                    self.info(f'duplicate packet {pkt.serial_number}, resending ACK')
                    ack = Packet(sn=self._next_expected_seq - 1, size=pkt.size, type=PacketType.ACK)
                    self._nic.send(ack)
            
            elif pkt.type == PacketType.ACK:
                if pkt.serial_number >= self._send_base:
                    self.info(f'received cumulative ACK {pkt.serial_number}')
                    
                    old_base = self._send_base
                    self._send_base = pkt.serial_number + 1
                    self.info(f'window slides from {old_base} to {self._send_base}')
                    
                    self._timer_active = False
                    
                    if self._send_base < self._next_seq_num:
                        self._start_timer()
                    
                    self._send_packets_in_window()
        
        elif self._mode == ReliabilityMode.PIPELINING_DYNAMIC_WINDOW:
            if pkt.type == PacketType.DATA:
                if pkt.serial_number == self._next_expected_seq:
                    self.info(f'received expected packet {pkt.serial_number}')
                    self._next_expected_seq += 1
                    
                    while self._next_expected_seq in self._receive_buffer:
                        self.info(f'delivering buffered packet {self._next_expected_seq}')
                        del self._receive_buffer[self._next_expected_seq]
                        self._next_expected_seq += 1
                    
                    ack = Packet(sn=self._next_expected_seq - 1, size=pkt.size, type=PacketType.ACK)
                    self.info(f'sending cumulative ACK {self._next_expected_seq - 1}')
                    self._nic.send(ack)
                
                elif pkt.serial_number > self._next_expected_seq:
                    self.info(f'packet {pkt.serial_number} out of order, buffering (expected {self._next_expected_seq})')
                    self._receive_buffer[pkt.serial_number] = pkt
                    
                    ack = Packet(sn=self._next_expected_seq - 1, size=pkt.size, type=PacketType.ACK)
                    self.info(f'sending cumulative ACK {self._next_expected_seq - 1}')
                    self._nic.send(ack)
                else:
                    self.info(f'duplicate packet {pkt.serial_number}, resending ACK')
                    ack = Packet(sn=self._next_expected_seq - 1, size=pkt.size, type=PacketType.ACK)
                    self._nic.send(ack)
            
            elif pkt.type == PacketType.ACK:
                if pkt.serial_number >= self._send_base:
                    self.info(f'received cumulative ACK {pkt.serial_number}')
                    
                    old_base = self._send_base
                    self._send_base = pkt.serial_number + 1
                    self.info(f'window slides from {old_base} to {self._send_base}')
                    
                    self._timer_active = False
                    
                    self._window_size += 1
                    self.info(f'window size increased to {self._window_size}')
                    
                    if self._send_base < self._next_seq_num:
                        self._start_timer()
                    
                    self._send_packets_in_window()
    
    def _timeout(self, pkt):
        if self._mode == ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION:
            if self._timer_active and pkt.serial_number == self._expected_ack:
                self.info(f'TIMEOUT for {pkt}, retransmitting')
                self._nic.send(pkt)
                self._sim.add_event(Event(pkt, self._timeout), self._timeout_delay)
        
        elif self._mode == ReliabilityMode.PIPELINING_FIXED_WINDOW:
            if self._timer_active:
                self.info(f'TIMEOUT for packet {self._send_base}, retransmitting')
                if self._send_base in self._packets_sent:
                    pkt_to_resend = self._packets_sent[self._send_base]
                    self._nic.send(pkt_to_resend)
                    self._start_timer()
        
        elif self._mode == ReliabilityMode.PIPELINING_DYNAMIC_WINDOW:
            if self._timer_active:
                self.info(f'TIMEOUT for packet {self._send_base}, retransmitting')
                
                self._window_size = 1
                self.info(f'window size decreased to {self._window_size}')
                
                if self._send_base in self._packets_sent:
                    pkt_to_resend = self._packets_sent[self._send_base]
                    self._nic.send(pkt_to_resend)
                    self._start_timer()
    
    def _start_timer(self):
        if self._send_base in self._packets_sent:
            self._timer_active = True
            pkt = self._packets_sent[self._send_base]
            self.info(f'starting timer for packet {self._send_base}')
            self._sim.add_event(Event(pkt, self._timeout), self._timeout_delay)
    
    def _send_packets_in_window(self):
        while self._next_seq_num < self._send_base + self._window_size and len(self._packets_to_send) > 0:
            pkt = self._packets_to_send.pop(0)
            self.info(f'sends {pkt} on {self._nic} [window: {self._send_base} to {self._send_base + self._window_size - 1}]')
            self._nic.send(pkt)
            self._packets_sent[pkt.serial_number] = pkt
            
            if pkt.serial_number == self._send_base:
                self._start_timer()
            
            self._next_seq_num = pkt.serial_number + 1
    
    def _send_next_packet(self):
        if self._mode == ReliabilityMode.ACKNOWLEDGES:
            if len(self._packets_to_send) > 0 and not self._waiting_for_ack:
                pkt = self._packets_to_send.pop(0)
                self.info(f'sends {pkt} on {self._nic}')
                self._nic.send(pkt)
                self._waiting_for_ack = True
                self._expected_ack = pkt.serial_number
        
        elif self._mode == ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION:
            if len(self._packets_to_send) > 0 and not self._waiting_for_ack:
                pkt = self._packets_to_send.pop(0)
                self.info(f'sends {pkt} on {self._nic}')
                self._nic.send(pkt)
                self._waiting_for_ack = True
                self._expected_ack = pkt.serial_number
                self._current_packet = pkt
                self._timer_active = True
                self.info(f'starting timer for {pkt.serial_number} ({self._timeout_delay}s)')
                self._sim.add_event(Event(pkt, self._timeout), self._timeout_delay)
    
    def send(self, pkts):
        if self._mode == ReliabilityMode.NO_RELIABILITY:
            for pkt in pkts:
                self.info(f'sends {pkt} on {self._nic}')
                self._nic.send(pkt)
        
        elif self._mode == ReliabilityMode.ACKNOWLEDGES or self._mode == ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION:
            self._packets_to_send = pkts.copy()
            self._send_next_packet()
        
        elif self._mode == ReliabilityMode.PIPELINING_FIXED_WINDOW:
            self._send_base = pkts[0].serial_number
            self._next_seq_num = pkts[0].serial_number
            self._next_expected_seq = pkts[0].serial_number
            self._packets_to_send = pkts.copy()
            self._send_packets_in_window()
        
        elif self._mode == ReliabilityMode.PIPELINING_DYNAMIC_WINDOW:
            self._window_size = 1
            self._send_base = pkts[0].serial_number
            self._next_seq_num = pkts[0].serial_number
            self._next_expected_seq = pkts[0].serial_number
            self._packets_to_send = pkts.copy()
            self._send_packets_in_window()
        
        else:
            raise NotImplementedError('This reliability mode is not yet implemented.')
        
    def __repr__(self):
        return f'Host({self._name})'