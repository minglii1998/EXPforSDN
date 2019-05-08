Exp 1
===
###### 具体实验要求可从文件`SDN_exp1.pdf`中查看
### 1. 选取自己名字中的任意⼀一个字，按照汉字的结构⽣生成mininet拓拓扑并连接Ryu
代码为`topo_li.py` <br>
我选取了‘李’字，由于文档中所提供得可视化界面只会显示switch而不会显示交换机，故在写拓扑过程中只写了switch。<br>
图片如下：<br>
**尚未加图片**
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
#### 2.1 代码具体解读`exp1_new_switch.py`



    
###### 这是除了`SDN_exp1.pdf`文件以外遇到的一些坑，或者值得记录的地方，其实还有很多，但是不想写了.先这样吧。
