from statistics import mode
from simulator.SimulatedEntity import SimulatedEntity
from enum import Enum
from Packet import Packet, PacketType

class ReliabilityMode(Enum):
    NO_RELIABILITY = 0
    ACKNOWLEDGES = 1
    ACKNOWLEDGES_WITH_RETRANSMISSION = 2
    PIPELINING_FIXED_WINDOW = 3
    PIPELINING_DYNAMIC_WINDOW = 4

class _TimeoutEvent:
    def __init__(self, callback):
        self._callback = callback

    def run(self):
        self._callback()

class Host(SimulatedEntity):
    
    def __init__(self, sim, name, mode=ReliabilityMode.NO_RELIABILITY):
        super().__init__(sim, logger_name='Hosts')
        self._name = name
        self._nic = None
        self._mode = mode

        # Stop-and-Wait (ACKNOWLEDGES)
        self._sw_send_queue = []     # les pacqets qu'il doit encore envoyer
        self._sw_waiting_ack = False # s'il attend un ACK d'un pacqet
        self._sw_current_pkt = None  # quel pacqet est actuellement en attente d'ACK

        # Retransmission timer (ACKNOWLEDGES WITH RETRANSMISSION)
        self._sw_rto = 0.01
        self._sw_timer_token = 0
        
    def add_nic(self, nic):
        assert nic.host() == None
        nic.set_host(self)
        self._nic = nic

    def _sw_start_timer(self, sn: int):
        # Démarre un timer pour le paquet en attente d'ACK
        self._sw_timer_token += 1
        token = self._sw_timer_token
        self.info(f'[SW] timer started for SN={sn} (RTO={self._sw_rto})')

        def on_timeout():
            self._sw_on_timeout(token, sn)

        self._sim.add_event(_TimeoutEvent(on_timeout), self._sw_rto)

    def _sw_stop_timer(self, sn: int):
        # Arrête le timer du paquet acquitté
        self._sw_timer_token += 1
        self.info(f'[SW] timer stopped for SN={sn}')

    def _sw_on_timeout(self, token: int, sn: int):
        # Retransmet le paquet lorsque le timer est expiré avec un nouveau timer
        if token != self._sw_timer_token:
            return
        
        if not self._sw_waiting_ack or self._sw_current_pkt is None:
            return
        
        if self._sw_current_pkt.serial_number != sn:
            return
        
        self.info(f'[SW] timer expired for sn={sn} -> retransmit {self._sw_current_pkt}')
        self._nic.send(self._sw_current_pkt)
        self._sw_start_timer(sn)

    def _sw_try_send_next(self):
        # Envoie le prochain paquet si on n'attends pas d'ACK
        if self._sw_waiting_ack:
            return
        if not self._sw_send_queue:
            return
        
        pkt = self._sw_send_queue.pop(0)
        self._sw_current_pkt = pkt
        self._sw_waiting_ack = True
        self.info(f'[SW] sends {pkt} on {self._nic} (waiting ACK)')
        self._nic.send(pkt)

        if self._mode == ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION:
            self._sw_start_timer(pkt.serial_number)
    
    def receive(self, nic, pkt):
        assert nic == self._nic
        self.info(f'received {pkt} on {nic}')

        # Stop-and-Wait avec ACK
        if self._mode in (ReliabilityMode.ACKNOWLEDGES, ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION):
            if pkt.type == PacketType.DATA:
                # Réception d'un paquet de type data -> renvoyer un ACK
                ack = Packet(sn=pkt.serial_number, size=pkt.size, type=PacketType.ACK)
                self.info(f'[SW] sends {ack} on {self._nic} (ACK for SN={pkt.serial_number})')
                self._nic.send(ack)
                return

            if pkt.type == PacketType.ACK:
                # Réception d'un ACK -> on envoie le paquet suivant
                if self._sw_waiting_ack and self._sw_current_pkt is not None:
                    if pkt.serial_number == self._sw_current_pkt.serial_number:
                        self.info(f'[SW] received expected ACK for SN={pkt.serial_number}')

                        if self._mode == ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION:
                            self._sw_stop_timer(pkt.serial_number)

                        self._sw_waiting_ack = False
                        self._sw_current_pkt = None
                        self._sw_try_send_next()
                    else:
                        # ACK inattendu
                        self.info(f'[SW] received unexpected ACK SN={pkt.serial_number} (ignored)')
            
                return
    
    def send(self, pkts):
        if self._mode == ReliabilityMode.NO_RELIABILITY:
            for pkt in pkts:
                self.info(f'sends {pkt} on {self._nic}')
                self._nic.send(pkt)
        
        elif self._mode in (ReliabilityMode.ACKNOWLEDGES, ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION):
            self._sw_send_queue.extend(pkts)
            self._sw_try_send_next()

        else:
            raise NotImplementedError('This reliability mode is not yet implemented.')
        
    def __repr__(self):
        return f'Host({self._name})'

