# SDN Experiment 2

[TOC]

## 1 前言

- 《软件定义网络》课程实验总计四次，这是第二次的实验指导书

- 实验完成情况可当场验收，可提交实验报告，鼓励当场验收

- 实验内容要求各位提前完成，机房现场主要负责答疑和验收

- 实验需独自完成，鼓励互相学习和交流，严禁抄袭

- 关于实验部分的疑问或反馈或Anything请发送邮件至：sdnexp2019@outlook.com

  标题格式：`cs60-小胖-关于xxx`

## 2 实验环境

与第一次实验相同

## 3 实验内容

第二次实验主要为设计性实验，要求各位在熟悉SDN的基本原理和RYU API的基础上解决下面问题

### 题目

假如你有一个笔友遍天下爱写信的朋友叫李华，她生活在1972年的UCLA，希望通过ARPAnet（世界第一个数据包交换网络，互联网的鼻祖，接入了25个研究机构，共计55条链路。具体拓扑见下图）发送一封Email给位于MIT的李明同学，现在需要你借助Ryu控制器编写Ryu APP帮助她

1. 为减少网络中节点的中转，希望找到一条从UCLA到MIT**跳数最少**的连接，输出经过的路线
2. 为了尽快发送Email，希望能找到一条从UCLA到MIT**时延最短**的连接，输出经过的路线及总的时延，利用Ping包的RTT验证你的结果（此问题选做）

![](https://ws2.sinaimg.cn/large/006tKfTcly1g1g71jutkuj31e20u0gsc.jpg)

### 说明

- 上述拓扑为ARPAnet1972.3，源自[The Internet Zoo](http://www.topology-zoo.org/), 借助[assessing-mininet](https://github.com/sjas/assessing-mininet.git)转化成Mininet拓扑，做了一些修改（加入时延，修改名称等）作为实验拓扑
- 上述拓扑中存在环路，你需要解决ARP包的洪泛问题，一种解决思路是：我们通过Ryu的API可以发现全局的拓扑信息，可以将交换机的端口信息记录下来，当控制器收到一个未学习的Arp Request时，直接发给所有交换机连接主机的那些端口，这样我们可以减少数据包在网络中的无意义的洪泛（减少了在交换机与交换机间的洪泛）
- Ryu通过LLDP报文发现拓扑中的交换机，主机发现则需要主机主动发包，相关API的使用参考如下：

```python
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller import ofp_event
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib import hub
from ryu.topology.api import get_all_host, get_all_link, get_all_switch


class NetworkAwareness(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkAwareness, self).__init__(*args, **kwargs)
        self.dpid_mac_port = {}
        self.topo_thread = hub.spawn(self._get_topology)

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

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)

    def _get_topology(self):
        while True:
            self.logger.info('\n\n\n')

            hosts = get_all_host(self)
            switches = get_all_switch(self)
            links = get_all_link(self)

            self.logger.info('hosts:')
            for hosts in hosts:
                self.logger.info(hosts.to_dict())

            self.logger.info('switches:')
            for switch in switches:
                self.logger.info(switch.to_dict())

            self.logger.info('links:')
            for link in links:
                self.logger.info(link.to_dict())
        
            hub.sleep(2)
```

测试结果如下图，提取下图中API打印的信息可查看Ryu源码`ryu/topology/switches.py`中类的定义，不必处理自行处理字典

![](https://ws1.sinaimg.cn/large/006tKfTcly1g1l6qa7wq3j31hv0u0qnd.jpg)

- 对于图的存储及最短路径算法，可自行实现，可使用现有的库（如[networkx](https://networkx.github.io/documentation/stable/index.html)）
- 测量链路时延的思路可参考下图（建议先完成基于跳数的最短路径转发后再做下面的部分）

![image-20190330225556221](https://ws3.sinaimg.cn/large/006tKfTcly1g1l7oxgd89j30r00g5751.jpg)

控制器将带有时间戳LLDP报文下发给S1，S1转发给S2，S2上传回控制器（即内圈红色箭头的路径），根据收到的时间和发送时间即可计算出*控制器经S1到S2再返回控制器的时延*，记为`lldp_delay_s12`

反之，*控制器经S2到S1再返回控制器的时延*，记为`lldp_delay_s21`

我们可以利用Echo Request/Reply报文求出*控制器到S1、S2的往返时延*，记为`echo_delay_s1`, `echo_delay_s2`

则S1到S2的时延$delay = (lldp\_delay\_s12 + lldp\_delay\_s21 - echo\_delay\_s1 - echo\_delay\_s2) / 2$

为此，我们需要对Ryu做如下修改：

1. `ryu/topology/Switches.py`的`PortData/__init__()`

`PortData`记录交换机的端口信息，我们需要增加`self.delay`属性记录上述的`lldp_delay`

`self.timestamp`为LLDP包在发送时被打上的时间戳，具体发送的逻辑查看源码

```python
  class PortData(object):
      def __init__(self, is_down, lldp_data):
          super(PortData, self).__init__()
          self.is_down = is_down
          self.lldp_data = lldp_data
          self.timestamp = None
          self.sent = 0
          self.delay = 0
```

2. `ryu/topology/Switches/lldp_packet_in_handler()`

`lldp_packet_in_handler()`处理接收到的LLDP包，在这里我们用收到LLDP报文的时间戳减去发送时的时间戳即为`lldp_delay`，由于LLDP报文被设计为经一跳后转给控制器，我们可将`lldp_delay`存入发送LLDP包对应的交换机端口

```python
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def lldp_packet_in_handler(self, ev):
    	# add receive timestamp
        recv_timestamp = time.time()
        if not self.link_discovery:
            return

        msg = ev.msg
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)
        except LLDPPacket.LLDPUnknownFormat:
            # This handler can receive all the packets which can be
            # not-LLDP packet. Ignore it silently
            return
        
        # calc the delay of lldp packet
        for port, port_data in self.ports.items():
            if src_dpid == port.dpid and src_port_no == port.port_no:
                send_timestamp = port_data.timestamp
                if send_timestamp:
                    port_data.delay = recv_timestamp - send_timestamp
        
        ...
```

**完成上述修改后需重新编译安装Ryu，在安装目录`~/sdn/ryu`下运行`sudo python setup.py install`**

3. 获取`lldp_delay`

在你们需要完成的计算时延的APP中，利用`lookup_service_brick`获取到正在运行的`switches`的实例（即步骤12中被我们修改的类），按如下的方式即可获取相应的`lldp_delay`

```python
    from ryu.base.app_manager import lookup_service_brick
    
    ...
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_hander(self, ev):
        msg = ev.msg
        dpid = msg.datapath.id
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)

            if self.switches is None:
                self.switches = lookup_service_brick('switches')

            for port in self.switches.ports.keys():
                if src_dpid == port.dpid and src_port_no == port.port_no:
                    lldp_delay[(src_dpid, dpid)] = self.switches.ports[port].delay
        except:
            return
```

- 代码书写注意Python的编码规范 ，`pip install autopep8`后VS Code或PyCharm等会有相应提示

- 验收（二选一，当场验收分数略高）

  - 当场验收：请指导老师查看运行结果和代码，讲解具体思路；仅提交源码以供查重
  - 提交报告：报告中需包括个人信息、思路分析、路径输出及总结（.pdf），同时附上源码

  压缩包命名格式`cs60-小胖-exp2`，提交至sdnexp2019@outlook.com

### 示例

- 跳数最少的连接

![](https://ws1.sinaimg.cn/large/006tKfTcly1g1lrrz9xqkj31oq0u07e5.jpg)

拓扑的打印不做要求，打印出经过的交换机即可

因为沉默主机的原因，前几次Ping会丢包为正常现象

- 时延最短的连接

![](https://ws2.sinaimg.cn/large/006tKfTcly1g1ls0ochj7j31rc0u0am1.jpg)

同样拓扑的打印不做要求，打印出经过的交换机和总的路径时延

总路径时延应约等于Ping包RTT的一半

## 4 参考

本次实验参考网络资料整理而成，参考内容后面附上

