EXP 2
====
###### 具体实验要求可从文件`SDN_exp2.pdf`中查看
### 1. Shortest Path
######  思路：利用生成树协议处理arp包在环路中的洪泛问题，利用`get_topo.py`得到网络拓扑结构，再利用networkx计算最短路径。
#### 1.1 ~~生成树协议 STP~~(和最短路径冲突..悲伤)
Details in [Spanning Tree in RyuBook](https://osrg.github.io/ryu-book/en/html/spanning_tree.html)
##### 1.1.1 原理
生成树协议STP(Spanning Tree Protocol)是用于在局域网中消除数据链路层物理环路的协议，
它通过在桥之间互相转换BPDU（Bridge Protocol Data Unit,桥协议数据单元），
来保证设备完成生成树的计算过程。<br>
Spanning Tree Protocol (STP: IEEE 802.1D) handles a network as a logical tree 
and by setting the ports of each switch (sometimes called a bridge in this section) 
to transfer frame or not it suppresses occurrence of broadcast streams in a network having a loop structure.
##### 1.1.2 步骤
###### 1 Selecting the root bridge<br>
The bridge having the smallest bridge ID is selected as the root bridge through BPDU packet exchange between bridges. 
After that, only the root bridge sends the original BPDU packet and other bridges transfer BPDU packets received from the root bridge.<br>
###### 2 Deciding the role of ports<br>
Based on the cost of each port to reach the root bridge, decide the role of the ports.<br>
###### 3 Port state change<br>
After the port role is decided (STP calculation is completed), each port becomes LISTEN state. 
After that, the state changes as shown below and according to the role of each port, 
it eventually becomes FORWARD state or BLOCK state. 
Ports set as disabled ports in the configuration become DISABLE state and after that the change of state does not take place.<br>
![](https://osrg.github.io/ryu-book/en/html/_images/fig33.png ''Port state change'')<br>
`DISABLE`	Disabled port. Ignores all received packets.<br>
`BLOCK`	  Receives BPDU only.<br>
`LISTEN`	Sends and receives BPDU.<br>
`LEARN`	  Sends and receives BPDU, learns MAC.<br>
`FORWARD`	Sends and receives BPDU, learns MAC, transfers frames.<br>
##### 1.1.3 对`SimpleSwitch13.py`的理解
* `stplib.py` is a library that provides spanning tree functions 
* `The simple_switch_stp_13.py` is an application program in which the spanning tree function is added to the switching hub application using the spanning tree library.
* 实际上这两个库不用知道太仔细，需要用到STP就直接无脑import就好了。
```python
class SimpleSwitch13(simple_switch_13.SimpleSwitch13):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'stplib': stplib.Stp}
```
*  _CONTEXTS = {'stplib': stplib.Stp} 
这句官方给的解释是 As with ” Link Aggregation ”, register CONTEXT to use the STP library. <br>
但是鉴于自己实在对SDN和RYU了解的不多，并不知道” Link Aggregation ”又是啥，所以当作固定用法的就好了。
```python
    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.stp = kwargs['stplib']

        # Sample of stplib config.
        #  please refer to stplib.Stp.set_config() for details.
        config = {dpid_lib.str_to_dpid('0000000000000001'):
                  {'bridge': {'priority': 0x8000}},
                  dpid_lib.str_to_dpid('0000000000000002'):
                  {'bridge': {'priority': 0x9000}},
                  dpid_lib.str_to_dpid('0000000000000003'):
                  {'bridge': {'priority': 0xa000}}}
        self.stp.set_config(config)
```
* config = {....}
这个是用于设置优先级，以优先级来决定谁才是root bridge，在上面的原理部分已经提过了。<br>
但是亲测这是不必要的，直接把config={...} 以及 下面的 Set_config 全部注释掉就行了。<br>
但是似乎如果在知道某个点作为起始的情况，是不是设置一下会更好？
*  self.stp = kwargs['stplib'] 
这个似乎也是可以删掉的，应该只有需要用到Config的话才需要这个语句。
```python
@set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
def _packet_in_handler(self, ev):
```
* @set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
一般用的都是`@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)`这里不同
官方解释：By using the stplib.EventPacketIn event defined in the STP library, 
it is possible to receive packets other than BPDU packets; 
therefore, the same packet handling is performed as ” Switching Hub ”.
```python
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
```
The change notification event (stplib.EventPortStateChange) of the port status is received 
and the debug log of the port status is output.<br>
但是我试了一下把这段全注释了，依然在运行时会出来logger信息，不懂。
###### 就这么把Ryubook上关于STP的部分全看完了，但是其实还是不太懂，没有涉及到其最底层的算法。
#### 1.2 STP与shortest path冲突分析
##### 1.2.1 出现的问题
在写完所有的代码后，即利用STP处理arp包洪范，然后用nx来得到最短路径并将包输出。但是会出现很玄学的问题，最短路径是可以打印出来的，但是并不是每次都能ping通，而且能否ping通完全靠运气，可能上一秒就可以，下一秒就又不行了。这个问题烦了我3.4天，心态爆炸，从来没有处理过类似的问题，从来不知道为什么同一个代码还能跑出不同的结果。
##### 1.2.2 问题初步分析
在修改获取最短路径的逻辑多次确认无误后，决定把目光投向stp。
###### 想法1：因为自己改了ryu的switch包，导致虚拟机环境配置出问题，程序运行不稳定。
试验：将代码在同学电脑上运行。<br>
结果：发现和在自己电脑上运行情况完全一样，故排除该可能性。
###### 想法2：生成树的根节点的选取会影响是否能ping通
试验：将MIT连接的switch25设置为权重最小的，因此每次得到生成树都是都是从该switch作为根节点生成。<br>
结果：和原来的没有任何差别，成功率反而下降了
###### 想法3：生成树协议直接改变了拓扑结构，使拓扑变成了树
结果：直接否定，因为最短路径每次都是可以算出来的，只是单纯的ping不通，若整个拓扑结构改变，那一定不会算出正确的路径。
###### ~~想法4：是自己人品太差了自暴自弃好了~~
##### 1.2.3 对代码输出结果的进一步测试
每次进入主逻辑后，都将目前的dp以及下一个dp以及输出端口号打印出来。<br>
发现，经常会卡在某一个节点，输出端口已经正确打印出，但是程序却并没有真的将这个包通过那个端口送出，并且每次卡主的地方不甚相同。
##### 1.2.4 对问题的进一步分析
重新阅读了ryu对stp的处理方式，注意到了最终某些端口会进入block状态，可能进入block状态后不仅仅会阻止arp包通过，任何包可能都会被阻塞。而且由于生成树的随机性，完全有可能出现有时候可以有时候不行的结果。
##### 1.2.5 验证
###### 方法：将每个包的ddp，next dp和out port都打印出来，并且查表看这个dp的out port是否处于block状态
![stop where](https://github.com/minglii1998/EXPforSDN/blob/master/exp2.2/sdn_exp2/pic/stp_wrong1.png)
![port state](https://github.com/minglii1998/EXPforSDN/blob/master/exp2.2/sdn_exp2/pic/stp_wrong.png)<br>
由上图1可见，我卡在了从dp20到dp19的过程，这时out port为3，然后从二图可见，dp为20（图中14为16进制的20）的3号端口处于block模式，由此可见，推论正确。
##### 1.2.6 结论与解决办法
###### 结论1：利用stp会将一些端口直接封死，而不是只对arp包限制，因此在计算出最短路径后，会因为有些端口被封住而无法通过。
###### 结论2：利用networkx的最短路径算法时，该算法不会考虑端口是否被block。
###### 解决方法：~~我刚了这么久了不想看了我选择死亡~~还能怎么办，换一种船新的arp处理办法啊。
#### 1.3 获取网络拓扑结构
##### 1.3.1 `get_topo.py`解释
###### 这是助教给的代码，但我没找到官方文档对获取拓扑结构的解释，所以...我的意思是下面都是我瞎编的...
```python
class NetworkAwareness(app_manager.RyuApp):
    ....
		self.topo_thread = hub.spawn(self._get_topology)
```
初始化时调用后面的`_get_topology()`函数。<br>至于 hub.spawn() ，我刚刚特意翻了源码，意思应该就是一直执行括号中的函数？
不太确定，我直接贴源码吧。<br>emmmm源码在虚拟机里贴不上来....<br>算了...
```python
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
 这就是前面所调用的用来获取拓扑结构的函数。
 * `get_all_XX()`是直接就定义好的，直接用即可
 * `self.logger.info()`这三段是用来检查输出信息的
 * `hub.sleep(2)`应该是和`hub.spawn`配合，每两秒运行一次这个函数
###### 但是在运行的过程中其实有两个小问题：
 ① `get_topo.py`只有在提前于mininet打开时才能获得正确的host，原因未知<br>
 ②在运行`get_topo.py`时一定要加上`--observe-links`，否则不能得到link
##### 1.3.2 获取拓扑结构的其他方式
```python
class get_topo(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
	def __init__(self, *args, **kwargs):
		super(get_topo, self).__init__(*args, **kwargs)
		self.topology_api_app = self

	@set_ev_cls(event.EventSwitchEnter)
	def get_topology(self, ev):
		switch_list = get_switch(self.topology_api_app, None)
		switches=[switch.dp.id for switch in switch_list]
		links_list = get_link(self.topology_api_app, None)
		links=[(link.src.dpid,link.dst.dpid,{'port':link.src.port_no}) for link in links_list]

		print "switches:%s" % switches
		print "links:%s" % links
```
就这么短短的，但是我一直没清楚他是什么时候调用`get_topology()`函数的，这个应该算是隐式的调用，上面那个是显示的。
* `self.topology_api_app = self`+`@set_ev_cls(event.EventSwitchEnter)`即可完成在每次连接switch时顺便获取其拓扑结构
#### 1.4 另一种处理arp包洪泛的方法
###### 详情参考[基于SDN的RYU应用开发之ARP代理](https://www.sdnlab.com/2318.html)
##### 1.4.1 大致思路
利用(dpid,原mac地址,目标ip)作为键值记录port,每个交换机第一次收到广播的arp时,记录,下一次收到键值相同但是port不同的arp广播包时,直接将包丢弃,因此便防止了同一个switch多次收到了同一个键值的包,避免了洪泛.
##### 1.4.2 `method_arp_flood.py`代码解读
```python
ETHERNET = ethernet.ethernet.__name__
ETHERNET_MULTICAST = "ff:ff:ff:ff:ff:ff"
ARP = arp.arp.__name__
```
* 命名一些全局变量
```python
    def __init__(self, *args, **kwargs):
        super(ARP_PROXY_13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.arp_table = {}
        self.sw = {}
```
* `arp_table`:[IP:mac_addr]用来存放ip和mac地址的对应
* `sw`:[(dpid,eth_src,arp_dst_ip):port]以(dpid,eth_src,arp_dst_ip)为键，每次确定一个port
```python
    def arp_handler(self, header_list, datapath, in_port, msg_buffer_id):
        header_list = header_list
        datapath = datapath
        in_port = in_port

        if ETHERNET in header_list:
            eth_dst = header_list[ETHERNET].dst
            eth_src = header_list[ETHERNET].src

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
```
* `header_list`:['types'...]用于存放需要处理的各种包的type以及各种其他变量，比如ip和mac
* `ETHERNET`是用来获得ip地址的
第二个if条件句真正开始对arp包进行处理<br>
如果要处理的包是arp包并且是广播来的，就对他进行处理。<br>
如果在sw中已经存在这个(datapath.id, eth_src, arp_dst_ip)三元键值，就直接把包丢弃，并返回true。<br>
如果没有则将该键值以及对应的port存储。<br>
* 该方法保证了每个switch只会收到一次由某个mac地址广播至某个ip地址的包
* 用目的ip而不是目的mac，是因为目的mac在第一次转播的过程是不知道的，但是目的ip是明确的
```python
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            if self.arp_handler(header_list, datapath, in_port, msg.buffer_id):
                # 1:reply or drop;  0: flood
                print "ARP_PROXY_13"
                return None
            else:
                out_port = ofproto.OFPP_FLOOD
                print 'OFPP_FLOOD'
```
这里可见，如果dst不在mac_to_port中，即代表此时目的mac是未知的，就需要处理arp包，若成功将多余的包丢弃，则打印ARP_PROXY_13.<br>
这里的代码用的依然是单纯的利用mac_to_port去学习,在简单的拓扑结构中是没问题的,但是在复杂的拓扑结构中,比如这次作业的拓扑结构中,就是无法正常运行的.
#### 1.5 主体获得最短路径的方法









