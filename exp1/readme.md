Exp 1
===
###### 具体实验要求可从文件`SDN_exp1.pdf`中查看
### 1. 选取自己名字中的任意⼀一个字，按照汉字的结构⽣生成mininet拓拓扑并连接Ryu
代码为`topo_li.py` <br>
我选取了‘李’字，由于文档中所提供得可视化界面只会显示switch而不会显示交换机，故在写拓扑过程中只写了switch。<br>
图片如下：<br>
![topo](https://github.com/minglii1998/EXPforSDN/blob/master/exp1/pic/sdn_exp1_topoli.png)
### 注意：
①. 写完拓扑结构运行时，一定要在命令行后面加上 `--controller remote`，否则ryu无法获得其拓扑结构。<br>
这个问题可能很蠢，但是对于初学者还是蛮致命的。要么在拓扑结构的py中写明为 `controller remote`，
要么在命令行后加`--controller remote`。<br>
加这一句，mininet才会和ryu连接，否则只会调用自带的pox控制器。<br>

### 2. 实现二层自学习交换机，避免数据包的洪泛
代码：<br>
`simple_switch.py`会将所有收到的包直接flood出去<br>
`exp1_new_switch.py`增加了自学习的过程，若有存放至`mac_to_port`中则直接发送到对应的端口，否则flood。<br>
#### 2.1 代码具体解读`simple_switch.py`
```python
class L2Switch(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    	
	def __init__(self, *args, **kwargs):
		super(L2Switch, self).__init__(*args, **kwargs)
```
* 定义这个switch的类，算是固定写法
* 通过`OFP_VERSIONS = []`来确定使用open flow的版本，这里为1.3
```python
	# handle packet_in message
	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	def packet_in_handler(self, ev):
		print "packet in"
		msg = ev.msg
		dp = msg.datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		
		actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
		out = parser.OFPPacketOut(
			datapath=dp, buffer_id=msg.buffer_id,
			in_port=msg.match['in_port'],actions=actions, data=msg.data)
		dp.send_msg(out)
		print "send ins finish"
```
* `@set_ev_cls()` tells Ryu when the decorated function should be called.The first argument of the decorator indicates which type of event this function should be called for. The second argument indicates the state of the switch.
从字面意思上也可以理解这两个参数，就是在交换机完成和控制器的连接后，每次有packet in时都会调用该函数。<br>
`HANDSHAKE_DISPATCHER`	Exchange of HELLO message<br>
`CONFIG_DISPATCHER`	Waiting to receive SwitchFeatures message<br>
`MAIN_DISPATCHER`	Normal status<br>
`DEAD_DISPATCHER`	Disconnection of connection<br>
* `ev.msg` is an object that represents a packet_in data structure.PDF中给的解释为：⽤用于携带触发事件的数据包。
* `msg.datapath` is an object that represents a datapath (switch).理解成和控制器连接的交换机就好了。
* `dp.ofproto` and `dp.ofproto_parser` are objects that represent the OpenFlow protocol that Ryu and the switch negotiated.定义了OpenFlow协议数据结构的对象，成员包含OpenFlow协议的数据结构，如动作类型
* `OFPActionOutput` class is used with a packet_out message to specify a switch port that you want to send the packet out of. 
* `OFPPacketOut` class is used to build a packet_out message.实际上就是将我们要传输的信息打包好。
* `actions`为我们规划的动作，建立动作时需要用`parser`。
* 这里的`in_port`与dp不同，dp是交换机，而port是交换机的端口。似乎从输出结果来看，大部分交换机都是3个端口的样子。
* 这个函数功能是直接让所有被送往控制器的包都直接flood出去
```python
	def add_flow(self, datapath, priority, match, actions):
		dp = datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser
		
		inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
actions)]
		mod = parser.OFPFlowMod(datapath=dp, priority=priority,
match=match, instructions=inst)
		dp.send_msg(mod)
		print "add flow finish"
```
* 该函数目的为对交换机增加新规则，需要由 Controller（Ryu）通过传送OFPFlowMod给 Switch，Switch 收到后将规则加入。
* `match`:这个交换机的match条件
* `inst`:match之后将执行的动作    
* `table`:规则要放在哪个table中 （这里没有，但是add_flow()函数经常需要） 
* `mod`：里应该有过一个参数为`command=ofp.OFPFC_ADD`，而删除就是`command=ofp.OFPFC_DELETE`，不过默认就是add。
* `dp_send_msg(mod)`:对switch新增规则    `dp_send_msg(out)`:告诉switch执行的动作
```python
	# add default flow table which sends packets to the controller
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
```
After handshake with the OpenFlow switch is completed, the Table-miss flow entry is added to the flow table to get ready to receive the Packet-In message.Specifically, upon receiving the Switch Features(Features Reply) message, the Table-miss flow entry is added.<br>
* `match=Parser.OFPMatch()`：产生match条件，若括号中无任何条件，则表示所有封包都会match此规则。
* `switch_features_handler(self, ev)`:这个基本属于固定写法，是在switch和controller连接时，对table加入规则，
    数据包会直接送入controller，并触发packet_in事件。
#### 2.2 代码具体解读`exp1_new_switch.py`
```python
	def __init__(self, *args, **kwargs):
		super(LearningSwitch, self).__init__(*args, **kwargs)
		self.mac_to_port={}
```
* 这里加了一个`self.mac_to_port`字典，用于存储每个dp对应的src或者dst的端口号，之后会细讲
```python
	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	def packet_in_handler(self, ev):
		...
		
		self.logger.info('packet: %s %s %s %s', dpid, src, dst, in_port)
		self.mac_to_port.setdefault(dpid,{})
		
		self.mac_to_port[dpid][src] = in_port
```
* `self.logger.info()`，将信息打印出来，和print不知道有什么区别，debug的好伙伴
* `self.mac_to_port.setdefault(dpid,{})`，初始化mac表，`setdefault()`功能为如果这个字典中没有健为dpid的，则初始化一个键为dpid的字典。（嵌套字典）
* `self.mac_to_port[dpid][src] = in_port`这句以dpid把src和端口号对应了起来，字典形如这样：{dpid:{src:in_port}}，但是要注意的是，src并不是一个键，它只是一个参数，在字典中src与dst没有区别，更像是这样：{dpid:{mac_addr:port}}。
![mac_to_port](https://github.com/minglii1998/EXPforSDN/blob/master/exp1/pic/sdn1_mactoport.png)
```python
	...
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD
	    
        actions = [parser.OFPActionOutput(out_port)]
	...
```
* 上面说清楚mac_to_port的结构后再看这部分代码应该挺好理解的，可以翻译为：<br>如果当前的这个交换机有存储目的的mac：<br>则输出端口即为这个mac对应的端口<br>否则：<br>flood<br>
```python
	...
	
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)
	    
	...    
```
* 这里是为了确立加入交换机的规则，下次就不用再询问控制器了<br>
比如：某个交换机从端口1收到了前往dst_9的包，然后通过控制器确定了我的out_port是3。那么下次我再从端口1收到了前往dst_9的包，就不用再问控制器了，而是直接根据这个规则将包从3号端口送出去即可。
```python
	...
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
	...
```
* 将数据包整合并发送出去，前面的代码只在交换机中加了规则。


##### END
