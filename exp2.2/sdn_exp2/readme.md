EXP 2
====
###### 具体实验要求可从文件`SDN_exp2.pdf`中查看
### 1. Shortest Path
######  思路：利用生成树协议处理arp包在环路中的洪泛问题，利用`get_topo.py`得到网络拓扑结构，再利用networkx计算最短路径。
#### 1.1 生成树协议 STP
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
#### 1.2 获取网络拓扑结构
##### 1.2.1 `get_topo.py`解释
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
##### 1.2.2 获取拓扑结构的其他方式
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
#### 1.3 最短路径主体




