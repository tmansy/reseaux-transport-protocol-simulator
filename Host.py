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
        self._sw_rto = 0.01         # timeout de retransmission
        self._sw_timer_token = 0    # token pour invalider les anciens timers

        # Pipelining fixed window (PFW)
        self._pfw_window_size = 5     # taille de la fenêtre (fixe)
        self._pfw_base = None         # SN du plus ancien paquet non acquitté
        self._pfw_next = None         # prochain SN à envoyer
        self._pfw_send_buf = {}       # paquets envoyés mais pas encore acquittés
        self._pfw_app_queue = []      # paquets DATA à envoyer
        self._pfw_rto = 0.01          # timeout de retransmission
        self._pfw_timer_token = 0     # token pour invalider les anciens timers
        self._pfw_expected = 1        # prochain SN attendu en ordre
        self._pfw_recv_cache = {}     # paquet reçus (hors ordre)

        # Pipelining dynamic window (PDW)
        self._pdw_window_size = 1     # taille de la fenêtre initialisée à 1
        self._pdw_base = None         # SN du plus ancien paquet non acquitté
        self._pdw_next = None         # prochain SN à envoyer
        self._pdw_send_buf = {}       # paquets envoyés mais pas encore acquittés
        self._pdw_app_queue = []      # paquets DATA à envoyer
        self._pdw_rto = 0.01          # timeout de retransmission
        self._pdw_timer_token = 0     # token pour invalider les anciens timers
        self._pdw_expected = 1        # prochain SN attendu en ordre
        self._pdw_recv_cache = {}     # paquets reçus (hors-ordre)

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

    def _pfw_start_timer(self):
        if self._pfw_base is None:
            return
        
        self._pfw_timer_token += 1
        token = self._pfw_timer_token
        base_sn = self._pfw_base
        self.info(f'[PFW] timer started for base SN={base_sn} (RTO={self._pfw_rto})')

        def _on_timeout():
            self._pfw_on_timeout(token, base_sn)

        self._sim.add_event(_TimeoutEvent(_on_timeout), self._pfw_rto)

    def _pfw_stop_timer(self):
        self._pfw_timer_token += 1
        self.info(f'[PFW] timer stopped')

    def _pfw_on_timeout(self, token: int, sn: int):
        if token != self._pfw_timer_token:
            return

        if self._pfw_base is None:
            return

        if sn != self._pfw_base:
            return

        pkt = self._pfw_send_buf.get(self._pfw_base)
        if pkt is None:
            return

        self.info(f'[PFW] timeout -> retransmit oldest unacked {pkt}')
        self._nic.send(pkt)
        self._pfw_start_timer()

    def _pfw_fill_window(self):
        # Remplit la fenêtre d'envoi tant que la fenêtre n'est pas pleine et qu'il reste des paquets à envoyer
        if self._pfw_base is None:
            # initialisation de la fenêtre du tout premier envoi
            if not self._pfw_app_queue:
                return
            first_sn = self._pfw_app_queue[0].serial_number
            self._pfw_base = first_sn
            self._pfw_next = first_sn

        while self._pfw_next is not None:
            in_flight = len(self._pfw_send_buf)
            if in_flight >= self._pfw_window_size:
                return
            if not self._pfw_app_queue:
                return
            
            pkt = self._pfw_app_queue[0]
            if pkt.serial_number != self._pfw_next:
                return
            
            self._pfw_app_queue.pop(0)
            self._pfw_send_buf[pkt.serial_number] = pkt

            self.info(f'[PFW] sends {pkt} (window base={self._pfw_base}, next={self._pfw_next}, height={self._pfw_window_size})')
            self._nic.send(pkt)

            if len(self._pfw_send_buf) == 1:
                self._pfw_start_timer()

            self._pfw_next += 1

    def _pfw_send_cum_ack(self):
        # Envoi d'un ack pour la gestion de la fenêtre
        ack_sn = self._pfw_expected - 1
        ack = Packet(sn=ack_sn, size=10, type=PacketType.ACK)
        self.info(f'[PFW] sends cumulative {ack} (ack up to SN={ack_sn})')
        self._nic.send(ack)

    def _pfw_on_data_received(self, pkt):
        # si le paquet est attendu => on avance expected et on délivre aussi ceux en cache
        # si paquet hors ordre => on le met en cache
        # si duplicata => on ignore
        # Puis on renvoie un ACK cumulatif.
        sn = pkt.serial_number

        if sn == self._pfw_expected:
            # Paquet ACK reçu dans le bon ordre
            self.info(f'[PFW] in-order DATA SN={sn} (expected={self._pfw_expected})')
            self._pfw_expected += 1

            while self._pfw_expected in self._pfw_recv_cache:
                cached = self._pfw_recv_cache.pop(self._pfw_expected)
                self.info(f'[PFW] deliver cached DATA SN={cached.serial_number}')
                self._pfw_expected += 1

        elif sn > self._pfw_expected:
            # Paquet reçu hors ordre
            if sn not in self._pfw_recv_cache:
                self._pfw_recv_cache[sn] = pkt
                self.info(f'[PFW] out-of-order DATA SN={sn} cached (expected={self._pfw_expected})')

        else:
            # Paquet ACK duplicata
            self.info(f'[PFW] duplicate DATA SN={sn} ignored (expected={self._pfw_expected})')

        self._pfw_send_cum_ack()

    def _pfw_on_ack_received(self, pkt):
        # Gestion de la fenêtre, du buffer et du timer
        ack_sn = pkt.serial_number
        if self._pfw_base is None:
            return

        if ack_sn < self._pfw_base - 1:
            self.info(f'[PFW] old ACK SN={ack_sn} ignored (base={self._pfw_base})')
            return

        newly_acked = [sn for sn in self._pfw_send_buf.keys() if sn <= ack_sn]
        if not newly_acked:
            self.info(f'[PFW] ACK SN={ack_sn} received (no new acked) (base={self._pfw_base})')
            return

        for sn in sorted(newly_acked):
            self._pfw_send_buf.pop(sn, None)

        old_base = self._pfw_base
        self._pfw_base = ack_sn + 1
        self.info(f'[PFW] cumulative ACK up to SN={ack_sn} -> slide window (base {old_base} -> {self._pfw_base})')

        if len(self._pfw_send_buf) == 0:
            self._pfw_stop_timer()
            self._pfw_base = None
            self._pfw_next = None
        else:
            self._pfw_start_timer()

        self._pfw_fill_window()

    def _pdw_start_timer(self):
        if self._pdw_base is None:
            return

        self._pdw_timer_token += 1
        token = self._pdw_timer_token
        base_sn = self._pdw_base
        self.info(f'[PDW] timer started for base SN={base_sn} (RTO={self._pdw_rto})')

        def _on_timeout():
            self._pdw_on_timeout(token, base_sn)

        self._sim.add_event(_TimeoutEvent(_on_timeout), self._pdw_rto)

    def _pdw_stop_timer(self):
        self._pdw_timer_token += 1
        self.info(f'[PDW] timer stopped')

    def _pdw_on_timeout(self, token: int, sn: int):
        if token != self._pdw_timer_token:
            return
        if self._pdw_base is None:
            return
        if sn != self._pdw_base:
            return

        old_w = self._pdw_window_size
        self._pdw_window_size = 1
        self.info(f'[PDW] timeout -> window size {old_w} -> {self._pdw_window_size}')

        # Retransmettre uniquement le plus ancien non acquitté
        pkt = self._pdw_send_buf.get(self._pdw_base)
        if pkt is None:
            return

        self.info(f'[PDW] timeout -> retransmit oldest unacked {pkt}')
        self._nic.send(pkt)

        # Redémarrer le timer
        self._pdw_start_timer()

    def _pdw_fill_window(self):
        # Initialisation base/next au premier envoi
        if self._pdw_base is None:
            if not self._pdw_app_queue:
                return
            first_sn = self._pdw_app_queue[0].serial_number
            self._pdw_base = first_sn
            self._pdw_next = first_sn

        while self._pdw_next is not None:
            in_flight = len(self._pdw_send_buf)
            if in_flight >= self._pdw_window_size:
                return
            if not self._pdw_app_queue:
                return

            pkt = self._pdw_app_queue[0]
            if pkt.serial_number != self._pdw_next:
                return

            self._pdw_app_queue.pop(0)
            self._pdw_send_buf[pkt.serial_number] = pkt

            self.info(f'[PDW] sends {pkt} (base={self._pdw_base}, next={self._pdw_next}, W={self._pdw_window_size})')
            self._nic.send(pkt)

            if len(self._pdw_send_buf) == 1:
                self._pdw_start_timer()

            self._pdw_next += 1

    def _pdw_send_cum_ack(self):
        ack_sn = self._pdw_expected - 1
        ack = Packet(sn=ack_sn, size=10, type=PacketType.ACK)
        self.info(f'[PDW] sends cumulative {ack} (ack up to SN={ack_sn})')
        self._nic.send(ack)

    def _pdw_on_data_received(self, pkt):
        sn = pkt.serial_number

        if sn == self._pdw_expected:
            self.info(f'[PDW] in-order DATA SN={sn} (expected={self._pdw_expected})')
            self._pdw_expected += 1

            while self._pdw_expected in self._pdw_recv_cache:
                cached = self._pdw_recv_cache.pop(self._pdw_expected)
                self.info(f'[PDW] deliver cached DATA SN={cached.serial_number}')
                self._pdw_expected += 1

        elif sn > self._pdw_expected:
            if sn not in self._pdw_recv_cache:
                self._pdw_recv_cache[sn] = pkt
                self.info(f'[PDW] out-of-order DATA SN={sn} cached (expected={self._pdw_expected})')
        else:
            self.info(f'[PDW] duplicate DATA SN={sn} ignored (expected={self._pdw_expected})')

        self._pdw_send_cum_ack()

    def _pdw_on_ack_received(self, pkt):
        ack_sn = pkt.serial_number
        if self._pdw_base is None:
            return

        if ack_sn < self._pdw_base - 1:
            self.info(f'[PDW] old ACK SN={ack_sn} ignored (base={self._pdw_base})')
            return

        newly_acked = [sn for sn in self._pdw_send_buf.keys() if sn <= ack_sn]
        if not newly_acked:
            self.info(f'[PDW] ACK SN={ack_sn} received (no new acked) (base={self._pdw_base})')
            return

        for sn in sorted(newly_acked):
            self._pdw_send_buf.pop(sn, None)

        old_w = self._pdw_window_size
        self._pdw_window_size += 1
        self.info(f'[PDW] ACK received -> window size {old_w} -> {self._pdw_window_size}')

        old_base = self._pdw_base
        self._pdw_base = ack_sn + 1
        self.info(f'[PDW] cumulative ACK up to SN={ack_sn} -> slide window (base {old_base} -> {self._pdw_base})')

        if len(self._pdw_send_buf) == 0:
            self._pdw_stop_timer()
            self._pdw_base = None
            self._pdw_next = None
        else:
            self._pdw_start_timer()

        self._pdw_fill_window()

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
        
        if self._mode == ReliabilityMode.PIPELINING_FIXED_WINDOW:
            if pkt.type == PacketType.DATA:
                self._pfw_on_data_received(pkt)
            elif pkt.type == PacketType.ACK:
                self._pfw_on_ack_received(pkt)
            return  

        if self._mode == ReliabilityMode.PIPELINING_DYNAMIC_WINDOW:
            if pkt.type == PacketType.DATA:
                self._pdw_on_data_received(pkt)
            elif pkt.type == PacketType.ACK:
                self._pdw_on_ack_received(pkt)
            return

    def send(self, pkts):
        if self._mode == ReliabilityMode.NO_RELIABILITY:
            for pkt in pkts:
                self.info(f'sends {pkt} on {self._nic}')
                self._nic.send(pkt)
        
        elif self._mode in (ReliabilityMode.ACKNOWLEDGES, ReliabilityMode.ACKNOWLEDGES_WITH_RETRANSMISSION):
            self._sw_send_queue.extend(pkts)
            self._sw_try_send_next()

        elif self._mode == ReliabilityMode.PIPELINING_FIXED_WINDOW:
            self._pfw_app_queue.extend(pkts)
            self._pfw_fill_window()
        
        elif self._mode == ReliabilityMode.PIPELINING_DYNAMIC_WINDOW:
            self._pdw_app_queue.extend(pkts)
            self._pdw_fill_window()

        else:
            raise NotImplementedError('This reliability mode is not yet implemented.')
        
    def __repr__(self):
        return f'Host({self._name})'

