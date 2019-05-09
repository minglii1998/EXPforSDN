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

class LearningSwitch(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
	_CONTEXTS = {'stplib': stplib.Stp}
	
	def __init__(self, *args, **kwargs):
		super(LearningSwitch, self).__init__(*args, **kwargs)
		self.mac_to_port={}
		self.switch_map = {}
		self.net = nx.DiGraph()
		self.stp = kwargs['stplib']
		config = {dpid_lib.str_to_dpid('0000000000000025'):
                  {'bridge': {'priority': 0x0000}}}
		self.stp.set_config(config)
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
		msg = ev.msg
		dp = msg.datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		self.switch_map.update({dp.id: dp})
		
		match = parser.OFPMatch()
		actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
			ofp.OFPCML_NO_BUFFER)]
		self.add_flow(dp, 0, match, actions)
		
	#@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	@set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
	def packet_in_handler(self, ev):
		
		msg = ev.msg
		dp = msg.datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		dpid = dp.id
		in_port = msg.match['in_port']
		
		pkt = packet.Packet(msg.data)
		eth_pkt = pkt.get_protocol(ethernet.ethernet)
		eth = pkt.get_protocol(ethernet.ethernet)

		dst = eth_pkt.dst
		src = eth_pkt.src
		
		if eth.ethertype == ether_types.ETH_TYPE_LLDP:
			#ignore lldp packet
			#print "here return"
			return
		
		if eth.ethertype == 34525:
			#ignore ipv6 packet
			#print "here return"
			return		
			

		self.mac_to_port.setdefault(dpid,{})
		
		self.mac_to_port[dpid][src] = in_port
		if dst in self.mac_to_port[dpid]:
			out_port = self.mac_to_port[dpid][dst]
			if src not in self.net:

				self.net.add_node(src)
				self.net.add_edge(dpid, src, port=in_port, weight=0)
				self.net.add_edge(src, dpid, weight=0)
				

			if dst in self.net:
				path = nx.shortest_path(self.net, src, dst, weight=0)
				print "path : %s" % path
				

				if  dpid in path:
					next = path[path.index(dpid) + 1]
					out_port = self.net[dpid][next]['port']
					
		else:
			out_port = ofp.OFPP_FLOOD
			pass
		

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
			
