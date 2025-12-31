from simulator.Simulator import Simulator
from Packet import Packet
from simulator.Event import Event

from NIC import NIC
from Host import Host, ReliabilityMode
from Router import Router

from Link import Link

import random
random.seed(2147483611)  # with this seed, the ACK for packet SN=10 is lost on Link L1

import logging

logging.basicConfig(format='[%(levelname)-5s] %(message)s')
logging.getLogger('simulator').setLevel(logging.INFO)
logging.getLogger('NIC').setLevel(logging.INFO)
logging.getLogger('Routers').setLevel(logging.INFO)
logging.getLogger('Hosts').setLevel(logging.INFO)

logging.getLogger('simulator').debug('Creating simulator...')
sim = Simulator()
sim.reset()

c = 3e8 # m/s

### Topology model ###
#                 L1            L2
#            (d_1, s_1)    (d_2, s_2)
#        [A]-----------[R]------------[B]
#                R_1           R_2

# Creating links L1 and L2
d1 = 1000  # m
s1 = 2/3*c # m/s
R1 = 1e6   # bps
L1 = Link("L1", distance=d1, speed=s1, lost_prob=0.02) # Link 1 with 2% packet loss

d2 = 1000  # m
s2 = 2/3*c # m/s
R2 = 5e5   # bps
L2 = Link("L2", distance=d2, speed=s2, lost_prob=0.02) # Link 2 with 2% packet loss

# Creating and configuring Host A and its NIC
nicA = NIC(sim, 'eth0', R1)
hostA = Host(sim, 'A', mode=ReliabilityMode.PIPELINING_FIXED_WINDOW)
hostA.add_nic(nicA)
nicA.attach(L1)

# Creating and configuring Router R and its NICs
nicL1 = NIC(sim, 'eth0', R1)
nicL2 = NIC(sim, 'eth1', R2, queue_size=20) # size of queue = 20 packets (when sending from A to B)
router = Router(sim, 'R')
router.add_nic(nicL1)
router.add_nic(nicL2)
nicL1.attach(L1)
nicL2.attach(L2)

# Creating and configuring Host B and its NIC
nicB = NIC(sim, 'eth0', R2)
hostB = Host(sim, 'B', mode=ReliabilityMode.PIPELINING_FIXED_WINDOW)
hostB.add_nic(nicB)
nicB.attach(L2)

packet_size = 10  # bytes
pkts = [Packet(sn=pkt_sn, size=packet_size) for pkt_sn in range(1, 51)]
hostA.send(pkts)

sim.run()