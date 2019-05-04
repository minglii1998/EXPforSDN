#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.node import Node
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.util import dumpNodeConnections
from mininet.term import makeTerm

if '__main__'== __name__ :

	net = Mininet(controller=RemoteController)
	c0 = net.addController('c0',ip='127.0.0.1', port=6633)

	s1 = net.addSwitch('s1')
	s2 = net.addSwitch('s2')
	s3 = net.addSwitch('s3')
	s4 = net.addSwitch('s4')
	s5 = net.addSwitch('s5')

	h1 = net.addHost('h1',mac='00:00:00:00:00:01')
	h2 = net.addHost('h2',mac='00:00:00:00:00:02')

		
	net.addLink(h1,s1)
	net.addLink( s1, s2 )
	net.addLink(s2,s3)
	net.addLink(s3,h2)
	net.addLink(h1,s4)
	net.addLink(s4,s5)
	net.addLink(s5,h2)

	#next two will cause loop
	#net.addLink(s5,s1)
	#net.addLink(s2,s4)

	net.build()

	c0.start()
	s1.start([c0])
	s2.start([c0])
	s3.start([c0])
	s4.start([c0])
	s5.start([c0])


	CLI(net)
	net.stop()