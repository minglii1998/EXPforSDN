#!/user/bin/python
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib import hub
from ryu.topology.api import get_all_host, get_all_link, get_all_switch
from ryu.topology import event, switches
import networkx as nx
import matplotlib.pyplot as plt
from ryu.app import simple_switch_13
from ryu.lib import stplib
from ryu.lib import dpid as dpid_lib
from ryu.base.app_manager import lookup_service_brick

class LearningSwitch(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
	_CONTEXTS = {'stplib': stplib.Stp}
	
	def __init__(self, *args, **kwargs):
		super(LearningSwitch, self).__init__(*args, **kwargs)
		self.mac_to_port={}
		self.switch_map = {}
		self.net = nx.DiGraph()
		self.stp = kwargs['stplib']
		self.topo_thread = hub.spawn(self._get_topology)
		
	def add_flow(self, datapath, priority, match, actions):
		dp = datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
			actions)]
		mod = parser.OFPFlowMod(datapath=dp, priority=priority,
			match=match, instructions=inst)
		dp.send_msg(mod)
		#print "add flow finished"
		
	def delete_flow(self, datapath):
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser

		for dst in self.mac_to_port[datapath.id].keys():
			match = parser.OFPMatch(eth_dst=dst)
			mod = parser.OFPFlowMod(
				datapath, command=ofproto.OFPFC_DELETE,
				out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
				priority=1, match=match)
			datapath.send_msg(mod)
	
	@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
	def switch_features_handler(self, ev):
		#print "switch hand"
		msg = ev.msg
		dp = msg.datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		self.switch_map.update({dp.id: dp})
		
		match = parser.OFPMatch()
		actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
			ofp.OFPCML_NO_BUFFER)]
		self.add_flow(dp, 0, match, actions)
		
	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	#@set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
	def packet_in_handler(self, ev):
		#print "packet in"
		msg = ev.msg
		dp = msg.datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		
		
		# the identity of switch
		dpid = dp.id
		# the port that receive the packet
		in_port = msg.match['in_port']
	
		
		pkt = packet.Packet(msg.data)
		eth_pkt = pkt.get_protocol(ethernet.ethernet)
		eth = pkt.get_protocol(ethernet.ethernet)
		# get the mac
		dst = eth_pkt.dst
		src = eth_pkt.src
		
		try:
			
			src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)
			print "first in"
			print "self switch : %s" %  self.switches
			if self.switches is None:
				self.switches = lookup_service_brick('switches')
			
			print "keys: %s" % self.switches.ports.keys()

			for port in self.switches.ports.keys():
				print "in"
				if src_dpid == port.dpid and src_port_no == port.port_no:
					lldp_delay[(src_dpid, dpid)] = self.switches.ports[port].delay
					print "src_dpid : %s" % src_dpid
					print "delay %s" % lldp_delay[(src_dpid, dpid)] 
					self.net[src_dpid][dpid]['delay'] = lldp_delay[(src_dpid, dpid)] 
		except:
			return
		
		#if eth.ethertype == ether_types.ETH_TYPE_LLDP:
			#ignore lldp packet
			#print "here return"
		#	return
		
		if eth.ethertype == 34525:
			#ignore ipv6 packet
			#print "here return"
			return
		'''
		print "src %s " % src
		print "dst %s " % dst
		print "in_port %s" % in_port
		print "dpid %s" %dpid		
		'''
		
		
		# we can use the logger to print some useful information
		#self.logger.info('packet: %s %s %s %s', dpid, src, dst, in_port)
		self.mac_to_port.setdefault(dpid,{})
		
		self.mac_to_port[dpid][src] = in_port
		if dst in self.mac_to_port[dpid]:
			out_port = self.mac_to_port[dpid][dst]
			if src not in self.net:
				#print "src %s not in self.net" % src
				#print "type %s" % eth.ethertype
				#print "dpid %s" % dpid
				self.net.add_node(src)
				self.net.add_edge(dpid, src, port=in_port, weight=0)
				self.net.add_edge(src, dpid, weight=0)
				#print (src in self.net)

			if dst in self.net:
				#print "dst %s in self.net" % dst
				
				path = nx.shortest_path(self.net, src, dst, weight="delay")
				#print "path dpid : %s" % dpid
				#self.logger.info('packet: %s %s %s %s', dpid, src, dst, in_port)
				print "path : %s" % path
				#print dpid in path

				if  dpid in path:
					next = path[path.index(dpid) + 1]
					'''
					print "in"
					print dpid in path
					print "next: %s" % next
					print "len path %s" % len(path)
					print "path now: %s" % path[path.index(dpid)]
					print "(%s,%s)" % (path[path.index(dpid)],next)
					'''
					
					out_port = self.net[dpid][next]['port']
			
		else:
			out_port = ofp.OFPP_FLOOD
			pass
		
		#print  self.mac_to_port[dpid]

		actions = [parser.OFPActionOutput(out_port)]

		if out_port != ofp.OFPP_FLOOD:
			match = parser.OFPMatch(in_port=in_port,eth_dst=dst)
			self.add_flow(dp,1,match,actions)

		data = None
		if msg.buffer_id == ofp.OFP_NO_BUFFER:
			data = msg.data
		
		out = parser.OFPPacketOut(
			datapath=dp, buffer_id=msg.buffer_id,
			in_port=in_port,actions=actions, data=msg.data)
		dp.send_msg(out)
		
		
	def _get_topology(self):
		while True:
			self.logger.info('\n')
			
			hosts = get_all_host(self)
			switch_list = get_all_switch(self)
			links_list = get_all_link(self)
			switches =[switch.dp.id for switch in switch_list]
			self.net.add_nodes_from(switches)
			links=[(link.src.dpid,link.dst.dpid,{'port':link.src.port_no}) for link in links_list]
			self.net.add_edges_from(links)
			hub.sleep(2)
			
	@set_ev_cls(stplib.EventTopologyChange, MAIN_DISPATCHER)
	def _topology_change_handler(self, ev):
		dp = ev.dp
		dpid_str = dpid_lib.dpid_to_str(dp.id)
		msg = 'Receive topology change event. Flush MAC table.'
		#self.logger.debug("[dpid=%s] %s", dpid_str, msg)

		if dp.id in self.mac_to_port:
			self.delete_flow(dp)
			del self.mac_to_port[dp.id]
	
	@set_ev_cls(stplib.EventPortStateChange, MAIN_DISPATCHER)
	def _port_state_change_handler(self, ev):
		dpid_str = dpid_lib.dpid_to_str(ev.dp.id)
		of_state = {stplib.PORT_STATE_DISABLE: 'DISABLE',
					stplib.PORT_STATE_BLOCK: 'BLOCK',
					stplib.PORT_STATE_LISTEN: 'LISTEN',
					stplib.PORT_STATE_LEARN: 'LEARN',
					stplib.PORT_STATE_FORWARD: 'FORWARD'}
		self.logger.debug("[dpid=%s][port=%d] state=%s",
					dpid_str, ev.port_no, of_state[ev.port_state])
			
