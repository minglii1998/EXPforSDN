#!/user/bin/python
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

class LearningSwitch(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
	
	def __init__(self, *args, **kwargs):
		super(LearningSwitch, self).__init__(*args, **kwargs)
		self.mac_to_port={}
		
	def add_flow(self, datapath, priority, match, actions):
		dp = datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
			actions)]
		mod = parser.OFPFlowMod(datapath=dp, priority=priority,
			match=match, instructions=inst)
		dp.send_msg(mod)
		print "add flow finished"
	
	@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
	def switch_features_handler(self, ev):
		print "switch hand"
		msg = ev.msg
		dp = msg.datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		
		match = parser.OFPMatch()
		actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
			ofp.OFPCML_NO_BUFFER)]
		self.add_flow(dp, 0, match, actions)
		
	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
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
		'''
		if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            #print "here return"
			return
		if eth.ethertype == 34525:
			#ignore 34525 packet
			#print "here return"
			return
		if eth.ethertype == 2054:
			#ignore 34525 packet
			#print "here return"
			return
		
		print "type: %s" % eth.ethertype
		'''
		# we can use the logger to print some useful information
		self.logger.info('packet: %s %s %s %s', dpid, src, dst, in_port)
		self.mac_to_port.setdefault(dpid,{})
		
		self.mac_to_port[dpid][src] = in_port
		if dst in self.mac_to_port[dpid]:
			out_port = self.mac_to_port[dpid][dst]
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