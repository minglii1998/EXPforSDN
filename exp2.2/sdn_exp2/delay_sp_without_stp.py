
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import arp, lldp

from ryu.lib import hub
from ryu.topology.api import get_all_host, get_all_link, get_all_switch
from ryu.topology import event, switches

import networkx as nx
import matplotlib.pyplot as plt

from ryu.base.app_manager import lookup_service_brick

ETHERNET = ethernet.ethernet.__name__
ETHERNET_MULTICAST = "ff:ff:ff:ff:ff:ff"
ARP = arp.arp.__name__


class ARP_PROXY_13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    

    def __init__(self, *args, **kwargs):
        super(ARP_PROXY_13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.arp_table = {}
        self.sw = {}
        self.switch_map = {}
        self.lldp_delay={}
        self.net = nx.DiGraph()
        self.switches = None
        self.topo_thread = hub.spawn(self._get_topology)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                idle_timeout=5, hard_timeout=15,
                                match=match, instructions=inst)
        datapath.send_msg(mod)
        
        
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


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        #print "packet in"
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        dpid = dp.id
        parser = dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src
        
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            src_dpid, src_port_no = switches.LLDPPacket.lldp_parse(msg.data)
            if self.switches is None:
                self.switches = app_manager.lookup_service_brick('switches')

            for port in self.switches.ports.keys():
                if src_dpid == port.dpid and src_port_no == port.port_no:
                    self.lldp_delay[(src_dpid,dpid)] = self.switches.ports[port].delay
                    a=self.lldp_delay[(src_dpid,dpid)]
                    self.net.add_edge(src_dpid,dpid,weight = a)
                    self.net.add_edge(dpid,src_dpid,weight = a)
                    #self.net[dpid][src_dpid]['weight'] = self.lldp_delay[(src_dpid,dpid)]

        
        
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
		
        if eth.ethertype == 34525:
            return
        
        
        header_list = dict(
            (p.protocol_name, p)for p in pkt.protocols if type(p) != str)
        if ARP in header_list:
            self.arp_table[header_list[ARP].src_ip] = src  # ARP learning
          
        #print header_list
        #print self.arp_table
        #print self.sw
        
        self.mac_to_port.setdefault(dpid, {})
        #self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port
        
        if src not in self.net:
            self.net.add_node(src)
            self.net.add_edge(dpid, src, port=in_port)
            self.net.add_edge(src, dpid)
        
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            if dst in self.net:
                path = nx.shortest_path(self.net, src, dst, weight='weight')
                print "path : %s" % path
                
                if  dpid in path:
                    next = path[path.index(dpid) + 1]
                    out_port = self.net[dpid][next]['port']
        
                
        else:
            if self.arp_handler(header_list, dp, in_port, msg.buffer_id):
            
                # 1:reply or drop;  0: flood
                print "ARP_PROXY_13"
                return None
            else:
                out_port = ofp.OFPP_FLOOD
                print 'OFPP_FLOOD'

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_icn next time
        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(dp, 1, match, actions)

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        dp.send_msg(out)

    def arp_handler(self, header_list, datapath, in_port, msg_buffer_id):
        header_list = header_list
        datapath = datapath
        in_port = in_port


        if ETHERNET in header_list:
            eth_dst = header_list[ETHERNET].dst
            eth_src = header_list[ETHERNET].src
        

        print header_list

        if eth_dst == ETHERNET_MULTICAST and ARP in header_list:
            arp_dst_ip = header_list[ARP].dst_ip

            if (datapath.id, eth_src, arp_dst_ip) in self.sw:  # Break the loop
                if self.sw[(datapath.id, eth_src, arp_dst_ip)] != in_port:

                    out = datapath.ofproto_parser.OFPPacketOut(
                        datapath=datapath,
                        buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                        in_port=in_port,
                        actions=[], data=None)
                    datapath.send_msg(out)
                    return True
            else:
                self.sw[(datapath.id, eth_src, arp_dst_ip)] = in_port
