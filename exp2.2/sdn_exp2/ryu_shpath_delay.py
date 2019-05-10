#!/usr/bin/python
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller import ofp_event
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import arp
from ryu.lib.packet import ether_types
from ryu.lib import hub
from ryu.lib import stplib
from ryu.topology import event,switches
from ryu.topology.api import get_switch, get_link
import networkx as nx
import matplotlib.pyplot as plt


ETHERNET = ethernet.ethernet.__name__
EHTERNET_MULTICAST = "ff:ff:ff:ff:ff:ff"
ARP = arp.arp.__name__


class NetworkAwareness(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    

    def __init__(self, *args, **kwargs):
        super(NetworkAwareness, self).__init__(*args, **kwargs)
        self.arp_table = {}
        self.sw = {}
        self.switch_map = {}
        self.net = nx.DiGraph()
        self.topology_api_app = self
        self.lldp_delay = {}
        self.switches = None
        

        
    def add_flow(self, datapath, priority, match, actions):
        dp = datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, match=match, instructions=inst)
        dp.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self.switch_map.update({dp.id:dp})
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)
        

    @set_ev_cls(event.EventSwitchEnter)
    def _get_topology_data(self,ev):
        switch_list = get_switch(self.topology_api_app, None)
        switches = [switch.dp.id for switch in switch_list]
        self.net.add_nodes_from(switches)
        
        print ("\n\n\n-----------List of switches")
        for switch in switch_list:
            # self.ls(switch)
            print (switch)
            # self.nodes[self.no_of_nodes] = switch
            # self.no_of_nodes += 1

        # -----------------------------
        links_list = get_link(self.topology_api_app, None)
        # for link in links_list:
        #     print link
        # print links_list
        links = [(link.src.dpid, link.dst.dpid, {'port': link.src.port_no}) for link in links_list]
        # print links
        self.net.add_edges_from(links)
        links = [(link.dst.dpid, link.src.dpid, {'port': link.dst.port_no}) for link in links_list]
        # print links
        self.net.add_edges_from(links)
        '''
        nx.draw(self.net, with_labels=True)
        plt.show()
        '''
        
        
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self,ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        
        
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            src_dpid, src_port_no = switches.LLDPPacket.lldp_parse(msg.data)
            if self.switches is None:
                self.switches = app_manager.lookup_service_brick('switches')

            for port in self.switches.ports.keys():
                if src_dpid == port.dpid and src_port_no == port.port_no:
                    self.lldp_delay[(src_dpid,dpid)] = self.switches.ports[port].delay
                    self.net[src_dpid][dpid]['weight'] = self.lldp_delay[(src_dpid,dpid)]
                    self.net[dpid][src_dpid]['weight'] = self.lldp_delay[(src_dpid,dpid)]
        
                

        
        if eth.ethertype == ether_types.ETH_TYPE_IPV6:
            #ignore lldp packet
            #print "here return"
            return
        
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            #ignore lldp packet
            #print "here return"
            return



        header_list = dict(
            (p.protocol_name, p) for p in pkt.protocols if type(p) != str
        )

        #print(header_list)


        #learning the match of source between ip and mac
        if ARP in header_list:
            self.logger.info("packet in %s %s %s", dpid, src, header_list[ARP].dst_ip)
            self.logger.info("---------ARP")
            self.arp_table[header_list[ARP].src_ip] = src
            #self.arp_handler(header_list, datapath, in_port, msg.buffer_id)
            if self.arp_handler(header_list, datapath, in_port, msg.buffer_id):
                print('ARP_PROXY')
                return None
            else:
                out_port = ofproto.OFPP_FLOOD
                self.logger.info("flood")
                

        if src not in self.net:
            self.net.add_node(src)
            self.net.add_edge(dpid, src, port = in_port)
            self.net.add_edge(src, dpid)

        if dst in self.net:
            path = nx.shortest_path(self.net, src, dst,weight = 'weight')
            next_match = parser.OFPMatch(eth_src = src,eth_dst=dst)		    
            back_match = parser.OFPMatch(eth_src = dst,eth_dst=src)
            print ("--------this is a shortest path------\n",path)
            total_delay = 0
            for on_path_switch in range(1, len(path)-1):
                now_switch = path[on_path_switch]
                next_switch = path[on_path_switch+1]
                back_switch = path[on_path_switch-1]
                next_port = self.net[now_switch][next_switch]['port']
                back_port = self.net[now_switch][back_switch]['port']
                if on_path_switch < len(path)-2:
                    total_delay = total_delay + self.net[now_switch][next_switch]['weight']
                
                action = [parser.OFPActionOutput(next_port)]
                self.add_flow(self.switch_map[now_switch], 100,next_match, action)
				
                action = [parser.OFPActionOutput(back_port)]
                self.add_flow(self.switch_map[now_switch], 100,back_match, action)
                print ("now switch:%s" % now_switch)
            print('total delay is:', total_delay)
            out_port = self.net[dpid][path[path.index(dpid)+1]]['port']
	    

        
        action = [parser.OFPActionOutput(out_port)]

        
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        
        out = parser.OFPPacketOut(datapath= datapath,buffer_id=msg.buffer_id,in_port=in_port,actions=action, data = data)
        datapath.send_msg(out)
                    


    def arp_handler(self, header_list, datapath, in_port, msg_buffer_id):
        header_list = header_list
        datapath = datapath
        in_port = in_port
 
        if ETHERNET in header_list:
            eth_dst = header_list[ETHERNET].dst
            eth_src = header_list[ETHERNET].src
 
        if eth_dst == EHTERNET_MULTICAST and ARP in header_list:
            arp_dst_ip = header_list[ARP].dst_ip
            if (datapath.id, eth_src, arp_dst_ip) in self.sw:  # Break the loop
                if self.sw[(datapath.id, eth_src, arp_dst_ip)] != in_port:
                    out = datapath.ofproto_parser.OFPPacketOut(
                        datapath=datapath,
                        buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                        in_port=in_port,
                        actions=[], data=None)
                    datapath.send_msg(out)
                    self.logger.info("----------------------drop---------------------------------")
                    return True
            else:
                self.sw[(datapath.id, eth_src, arp_dst_ip)] = in_port
                return False
        '''
        if ARP in header_list:
            hwtype = header_list[ARP].hwtype
            proto = header_list[ARP].proto
            hlen = header_list[ARP].hlen
            plen = header_list[ARP].plen
            opcode = header_list[ARP].opcode
            self.logger.info("------------------------opcode %s",opcode)
 
            arp_src_ip = header_list[ARP].src_ip
            arp_dst_ip = header_list[ARP].dst_ip
 
            actions = []
 
            if opcode == arp.ARP_REQUEST:
                if arp_dst_ip in self.arp_table:  # arp reply
                    actions.append(datapath.ofproto_parser.OFPActionOutput(
                        in_port)
                    )
 
                    ARP_Reply = packet.Packet()
                    ARP_Reply.add_protocol(ethernet.ethernet(
                        ethertype=header_list[ETHERNET].ethertype,
                        dst=eth_src,
                        src=self.arp_table[arp_dst_ip]))
                    ARP_Reply.add_protocol(arp.arp(
                        opcode=arp.ARP_REPLY,
                        src_mac=self.arp_table[arp_dst_ip],
                        src_ip=arp_dst_ip,
                        dst_mac=eth_src,
                        dst_ip=arp_src_ip))
 
                    ARP_Reply.serialize()
 
                    out = datapath.ofproto_parser.OFPPacketOut(
                        datapath=datapath,
                        buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                        in_port=datapath.ofproto.OFPP_CONTROLLER,
                        actions=actions, data=ARP_Reply.data)
                    datapath.send_msg(out)
                    self.logger.info("-----------------------reply---------------------------------")
                    return True
            '''
        
