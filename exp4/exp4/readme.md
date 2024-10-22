EXP 4
====
###### 具体实验要求可从文件`SDN_exp4.pdf`中查看
<!-- TOC -->

- [0. 环境与拓扑结构](#0-环境与拓扑结构)
- [1. 动态改变转发规则](#1-动态改变转发规则)
    - [1.1 要求](#11-要求)
    - [1.2 `dynamic_rules.py`代码解读](#12-dynamic_rulespy代码解读)
            - [获取拓扑结构](#获取拓扑结构)
        - [计算最短路径](#计算最短路径)
        - [install_path](#install_path)
        - [_packet_in_handler](#_packet_in_handler)
    - [1.3 思路分析](#13-思路分析)
        - [1.3.1 思路](#131-思路)
        - [1.3.1 实现](#131-实现)
    - [1.3 代码实现](#13-代码实现)
        - [获取最长路径：方法1](#获取最长路径方法1)
        - [获取最长路径：方法3](#获取最长路径方法3)
        - [获取最长路径：方法4](#获取最长路径方法4)
- [2. 链路故障恢复功能](#2-链路故障恢复功能)
    - [2.1 要求](#21-要求)
    - [2.2 思路](#22-思路)
    - [2.3 代码实现](#23-代码实现)
        - [删除流表](#删除流表)
        - [获得变动信息](#获得变动信息)
    - [2.4 结果展示](#24-结果展示)
- [3 负载均衡](#3-负载均衡)
    - [3.1 组表介绍](#31-组表介绍)
        - [3.1.1 组表构成](#311-组表构成)
        - [3.1.2 组表类型](#312-组表类型)
            - [【插入图片】](#插入图片)
    - [3.2 思路](#32-思路)
        - [3.2.1 获取从h1到h2的所有路径](#321-获取从h1到h2的所有路径)
        - [3.2.2 对路径上的每个switch，计算有几个出端口](#322-对路径上的每个switch计算有几个出端口)
        - [3.2.3 对于有两个及以上出端口的switch，添加组表](#323-对于有两个及以上出端口的switch添加组表)
    - [3.3 代码`load_balance.py`](#33-代码load_balancepy)
        - [3.3.1 整体情况](#331-整体情况)
        - [3.3.2 部分代码](#332-部分代码)
    - [3.4 结果展示](#34-结果展示)
        - [3.4.1 switch1 和 switch 5组表](#341-switch1-和-switch-5组表)
        - [3.4.2 各个端口发送总数](#342-各个端口发送总数)
            - [实验组：](#实验组)
            - [对照组：](#对照组)
- [4. 总结](#4-总结)

<!-- /TOC -->
### 0. 环境与拓扑结构
环境与第一次第二次实验相同，拓扑结构如图：
![topo](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/topo.png)
### 1. 动态改变转发规则
#### 1.1 要求
h1 ping h2，初始的路由规则为s1-s4-s5，5秒后，路由转发规则变为s1-s2-s3-s5，再过5秒后，转发规则又回到最初的s1-s4-s5，通
过这个循环调度的例子动态的改变交换机的转发规则<br>
#### 1.2 `dynamic_rules.py`代码解读
该代码为该次实验提供了大部分可直接调用的接口
###### 获取拓扑结构
```python
    def get_topology(self, ev):
        links_list = get_link(self.topology_api_app, None)
        self.src_links.clear()
        for link in links_list:
            sw_src = link.src.dpid
            sw_dst = link.dst.dpid
            src_port = link.src.port_no
            dst_port = link.dst.port_no
            src_port_name = link.src.name
            dst_port_name = link.dst.name
            self.port_name_to_num[src_port_name] = src_port
            self.port_name_to_num[dst_port_name] = dst_port
            self.src_links[sw_src][(sw_src, sw_dst)] = (src_port, dst_port)
            self.src_links[sw_dst][(sw_dst, sw_src)] = (dst_port, src_port)
```
* `self.src_links`：{dpid1:{(dpid1,dpid2):(port1,port2)}}，最终获取的拓扑结构都存入了该字典，存入的都是单独交换机与交换机的link，
比如：Switch1的2号端口连接到Switch2的3号端口，则该字典中存储{1:{(1,2):(2,3)}}，通过第一层的key值1可找到连接所有Switch1的交换机，
通过二层key值(1,2)可得到相关端口信息。
* 这是利用无向图存储拓扑信息的方式，每条链接需要4个参数来确定，而若用有向图存储，则每条链接需要存储2次，每次需要3个参数，实验2用的是有向图存储
* `self.port_name_to_num`：{name:port}，在本次实验中似乎并没有用到该全局变量
##### 计算最短路径
```python
    def short_path(self, src, dst, bw=0):
        if src == dst:
            return []
        result = defaultdict(lambda: defaultdict(lambda: None))
        distance = defaultdict(lambda: defaultdict(lambda: None))

        # the node is checked
        seen = [src]

        # the distance to src
        distance[src] = 0

        w = 1  # weight
        while len(seen) < len(self.src_links):
            node = seen[-1]
            if node == dst:
                break
            for (temp_src, temp_dst) in self.src_links[node]:
                if temp_dst not in seen:
                    temp_src_port = self.src_links[node][(temp_src, temp_dst)][0]
                    temp_dst_port = self.src_links[node][(temp_src, temp_dst)][1]
                    if (distance[temp_dst] is None) or (distance[temp_dst] > distance[temp_src] + w):
                        distance[temp_dst] = distance[temp_src] + w
                        # result = {"dpid":(link_src, src_port, link_dst, dst_port)}
                        result[temp_dst] = (temp_src, temp_src_port, temp_dst, temp_dst_port)
            min_node = None
            min_path = 999
            # get the min_path node
            for temp_node in distance:
                if (temp_node not in seen) and (distance[temp_node] is not None):
                    if distance[temp_node] < min_path:
                        min_node = temp_node
                        min_path = distance[temp_node]
            if min_node is None:
                break
            seen.append(min_node)

        path = []

        if dst not in result:
            return None

        while (dst in result) and (result[dst] is not None):
            path = [result[dst][2:4]] + path
            path = [result[dst][0:2]] + path
            dst = result[dst][0]
        #self.logger.info("path : %s", str(path))
        return path
```
* 这是最短路径的完整算法了，在第二次实验中我直接用的是networkx的内置函数，这个方法也是有参考意义的
* defaultdict(lambda: defaultdict(lambda: None))，这个的用法蛮奇特的，为设定默认的value值，
eg，a=defaultdict(lambda:3)，接下来输入任何为给定的key值，如a[2],a['a']，得到的都是3
* `result`：{dpid2:{dpid1,port1,dpid2,port2}}，通过key值dpid可到到所有连接着该dpid的switch以及相关端口
* `distance`：{dpid:int}，通过key可得从初始路径到达该点时的距离
* `seen[-1]`表示seen的最后一个元素
* 在第一个for循环中，得到的distance已经是最小了，因为第二个if条件句中有` (distance[temp_dst] > distance[temp_src] + w)`，说明只要存在distance[]中的值比现在找到的值更大，则用小的值替换,此时的result为已经排序好的，从src到dst的路径
* 第二个for循环是为了获得seen的下一个值
* `path`：{(dpid,port)}，由于result已经排序好了，故可以直接获得
##### install_path
```python
    def install_path(self, src_dpid, dst_dpid, src_port, dst_port, ev, src, dst, pkt_ipv4, pkt_tcp):
        
        ...
       
        mid_path = None
        mid_path = self.short_path(src=src_dpid, dst=dst_dpid)

        if mid_path is None:
            return
        self.path = None
        self.path = [(src_dpid, src_port)] + mid_path + [(dst_dpid, dst_port)]

        self.logger.info("path : %s", str(self.path))
        
        for i in xrange(len(self.path) - 2, -1, -2):
            datapath_path = self.datapaths[self.path[i][0]]
            match = parser.OFPMatch(in_port=self.path[i][1], eth_src=src, eth_dst=dst, eth_type=0x0800,
                                    ipv4_src=pkt_ipv4.src, ipv4_dst=pkt_ipv4.dst)

            if i < (len(self.path) - 2):
                actions = [parser.OFPActionOutput(self.path[i + 1][1])]
            else:
                actions = [parser.OFPActionSetField(eth_dst=self.ip_to_mac.get(pkt_ipv4.dst)),
                            parser.OFPActionOutput(self.path[i + 1][1])]
            
            self.add_flow(datapath_path, 100, match, actions, idle_timeout=5, hard_timeout=0)
```            
* `self.path`：{(dpid,port)}，eg，[(1,1),(1,3),(4,1),(4,2),(5,3),(5,1)]，表示从s1的1号端口进入，然后s1的3号端口发送给s4的1号端口，再从s4的2哈端口发送给s5的3号端口，再从s5的1号端口发出
* `xrange`等同于python3的`range`第一个参数为起始，第二个为结束，第三个为步长，即为从后往前将match，action都设定好，然后add_flow添加流表
* `idle_timeout`为空闲超时，指在指定时间之内若流表没有匹配任何报文则将此流表删除
* `hard_timeout`为硬超时，指自流表下发之后开始，经过指定时间之后无条件将流表删除
##### _packet_in_handler
* 代码较长，就不贴了，这里提供了arp flood的另一种办法，结合实验2中我用的两种方法，就可以有3中方法了，开森
#### 1.3 思路分析
##### 1.3.1 思路
1. 利用hard_timeout，将其设为5，即每5秒交换机上的流表就会被删除，此时交换机会重新向控制器询问
2. 再次询问时，改变install_path的路径
##### 1.3.1 实现
1. 需要一个计算长路径的算法，得到最长路径（4种方法）
   1. 直接修改short_path，将weight改为-1
   此时计算原来最短路径的算法就会就会直接变成最长路径<br>
   因为此时跳数越长反而路径长度越小，因此即可以得到跳数最多的路径，即题目中的最长路径
   2. 利用深度优先搜索<br>
   由于该题拓扑结构的特殊性（成环），因此利用深度优先算法可以得到一条将所有节点都串成一条的路径，s1-s2-s3-s5-s4或者s1-s4-s5-s3-s2，此时可直接将路径从s5处分开，即可得到两条长短不一的路径，再对比其长度即可得到短路径和长路径
   3. 直接修改short_path，将判断最小换成判断最大<br>
   ps:原以为这个方法不行，因为有环的存在，可能导致路径不停地绕环，最后发现当目的地一抵达，就会立刻退出循环，故不必担心
   4. 拓扑已知，故可以直接将路径写死
2. 需要一个全局变量来保存两种模式
3. 需要一个变量来判断目前的询问是第几次，并判断究竟该install长路径还是短路径（2种方法）
   1. 利用系统时间<br>
   交换机在获得流表后，就不会再向控制器询问，直到5秒后交换机流表被删除，此时才会再次向控制器询问<br>
   因此可以每次在install_path时都获得一下当前时间，跟上一次的时间对比，若有一定长度，如超过3秒，就可以认为此时应该转换mod<br>
   每次超过3秒都会counting+1，然后取模counting判断mod
   2. 利用install_flow的次数<br>
   交换机在每次请求时，所需要install path的次数是固定的2次，因此可知每4次为1个周期，然后通过取模判断mod就ok了
#### 1.3 代码实现
##### 获取最长路径：方法1
```python
    def long_path(self, src, dst, bw=0):
    ...
        w = -1  # weight
    ...
```
* 虽然是只加了一个负号，但是这个方法的确是很神奇的，当时第一次听到这个方法时，就觉得提出来的人太聪明了，但是如果不假思索，理所当然地改成负号然后不知道原理，就很没意思。
* ps：之所以这么说是因为在实验室的时候，一个人在跟另一个人解释为什么改weight就变成了最长路径，一直解释不清楚，甚至weight到底怎么改，是把1改成0还是-1都说不清楚，就在那里理所当然地说，改一下就好了，让我觉得有点emmmm不太好吧。
##### 获取最长路径：方法3
```python
    def long_path(self, src, dst, bw=0):
    ...
            max_node = None
            max_path = 0
            # get the max_path node
            for temp_node in distance:
                if (temp_node not in seen) and (distance[temp_node] is not None):
                    if distance[temp_node] > max_path:
                        mmax_node = temp_node
                        max_path = distance[temp_node]
            if max_node is None:
                break
            seen.append(max_node)
    ...
```
* 这个方法只是将原来的min_path=999改成了max_path=0，然后把min全改成了max，最后修改第一个if条件句中的‘<’改成‘>’就可以了
* 充分利用已有的代码
##### 获取最长路径：方法4
```python
    def long_path(self, src, dst, bw=0):
        if src == dst:
            return []

        result = defaultdict(lambda: defaultdict(lambda: None))
        if src==1 and dst == 5:
            fixed_path=[(1,2),(2,3),(3,5)]
        elif src == 5 and dst == 1:
            fixed_path=[(5,3),(3,2),(2,1)]

        for (temp_src, temp_dst) in fixed_path:
            if (temp_src, temp_dst) in self.src_links[temp_src]:
                temp_src_port = self.src_links[temp_src][(temp_src, temp_dst)][0]
                temp_dst_port = self.src_links[temp_src][(temp_src, temp_dst)][1]
                result[temp_dst] = (temp_src, temp_src_port, temp_dst, temp_dst_port)

        path = []
        if dst not in result:
            return None
        while (dst in result) and (result[dst] is not None):
            path = [result[dst][2:4]] + path
            path = [result[dst][0:2]] + path
            dst = result[dst][0]
        #self.logger.info("path : %s", str(path))
        return path
 ``` 
* 这里可看到`fixed_path`，为已经写好的路径，需要判断到底是往那个方向
* 后面的两个循环为将long_path的格式调成和short_path一样
* 该方法为第一次测试时使用的
##### 判断模式：方法1
```python 
    def __init__(self, *args, **kwargs):
    ...
        self.last_time=datetime.now()
        self.counting=0
        self.pathmod = 0 #0:short,1:long
    ...    
```
* 加入了这3个变量
* `self.last_time`：记录上一次的时间，用来和现在时间进行对比，判断是否需要转换模式
* `self.counting`：每次时间判断成功，都将该变量+1，通过取模得到mod
* `self.pathmod`：若为0则短路径，1则长路径
```python
    def install_path(self, src_dpid, dst_dpid, src_port, dst_port, ev, src, dst, pkt_ipv4, pkt_tcp):
    ...
        nowtime = datetime.now()
        if nowtime - self.last_time > timedelta(seconds=3):
            self.counting = self.counting + 1
        
        self.last_time=nowtime

        if self.counting %2 == 0:
            self.pathmod = 0
        elif self.counting %2 == 1:
            self.pathmod = 1
       
        mid_path = None
        if self.pathmod == 0:
            mid_path = self.short_path(src=src_dpid, dst=dst_dpid)
        else:
            mid_path = self.long_path(src=src_dpid, dst=dst_dpid)
    ...
```
* `nowtime`：获取当前时间
* if条件句判断时间是否已经过了3秒，若过了3秒，则技术加一
* 后面即通过取模判断模式
##### 判断模式：方法2
```python
    def install_path(self, src_dpid, dst_dpid, src_port, dst_port, ev, src, dst, pkt_ipv4, pkt_tcp):
    ...
        if self.counting %4 == 0 or self.counting %4 == 1:
            self.pathmod = 0
        elif self.counting %4 == 2 or self.counting %4 == 3:
            self.pathmod = 1
        self.counting = self.counting + 1
    ...
```
* 由于每次switch每次询问都会install两次（一个来回），故可得知每四次是一个循环，循环的前两次为短路径，后两次为长路径
#### 1.4 结果展示
打开topo指令：`sudo python topo.py --controller-remote`<br>
打开控制器指令：`sudo ryu_manager own_dynamic_rules.py --observe-links`
![result](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E5%AE%9E%E9%AA%8C1%E7%BB%93%E6%9E%9C.png)
* 左边为mininet，右边为控制器，右边为一个动态的过程，每隔5秒会打印另外一条路径
### 2. 链路故障恢复功能
#### 2.1 要求
在上图所示的拓扑结构中，h1到h2有两条通路，若其中正在进行传输的路径因为发生故障而断开连接，系统应当及时作出反应，改变转发
规则到另外一条路径上；若故障修复，系统也应当即时作出反应，改变转发规则到优先级较高的路径上
#### 2.2 思路
1. 控制器要能判断有link被down了
2. 在某一条link被down之后，交换机中有关这条路线的流表应该被清除，否则可能会导致交换机按照原来的流表传送信息，就会卡在断掉的link处
3. 交换机失去流表后，就会向控制器询问路径，此时只要继续用最短路径算法计算目前拓扑情况下的最短路径即可
4. 对于priority，个人觉得并不重要，因为无论何时交换机变动，控制器都会计算最短路径，所以不需要priority也可完成
5. 若需要priority，可将priority设为`100-len(self.path)`，因为路径越短priority越高，因此需要在前面加上负号，但是又因为priority必须为正，因此再加上100，当然，若知道路径会很长，就加上1000、10000甚至更多都可以。这种方法与固定的priority值相比有不好少好处：
   1. 不用去额外为每条路径设置priority
   2. 在匹配priority时，不需要查阅这条路径的priority是多少，不管是匹配或者加载，都只要令priority=100-len(self.path)即可
   3. 非常适用于路径数量较多的情况。eg，若是第二次实验的拓扑，人工为每条路径加上priority是不可能的，因此可直接用该方法
   4. 此方法也适用于带权的路径，只要把len从计算跳数变成计算整条路径的长度即可
   5. 潜在缺点：若两个路径长度相同，该方法会将其设为相同的优先级，但是一般情况若两条路径长度都一样，优先级相同似乎也无可厚非
#### 2.3 代码实现
##### 删除流表
```python
    def delete_flow(self, datapath,match):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        cookie = cookie_mask = 0
        table_id = 0
        priority=101
        idle_timeout = 15
        hard_timeout = 60
        buffer_id = ofp.OFP_NO_BUFFER
        actions = []
        inst = []
        req = ofp_parser.OFPFlowMod(datapath, 
                                cookie, cookie_mask, table_id, 
                                ofp.OFPFC_DELETE, idle_timeout, 
                                hard_timeout, priority, buffer_id, 
                                ofp.OFPP_ANY, ofp.OFPG_ANY, ofp.OFPFF_SEND_FLOW_REM, 
                                match, inst)
        datapath.send_msg(req)
```
* 删除流表的实现`delete_flow`其实大同小异，且与`add_flow`很相似，具体如何传参要看自己打算如何匹配
* `delete_flow()`的参数`datapath`表示要删除哪一个交换机的流表，`match`表示要删除该交换机满足什么条件的流表
* `ofp_parser.OFPFlowMod()`中有参数`ofp.OFPFC_DELETE`则为删除流表，若缺省则默认为增加流表
* `ofp_parser.OFPFlowMod()`中参数很多，似乎不一定可以缺省，以防万一，即使用不到也都写上吧
##### 获得变动信息
```python
    @set_ev_cls(ofp_event.EventOFPPortStatus, [CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, HANDSHAKE_DISPATCHER])
    def get_OFPPortStatus_msg(self, ev):
    
        msg=ev.msg
        datapath=ev.msg.datapath
        dpid = msg.datapath.id
        ofproto=datapath.ofproto
        parser = datapath.ofproto_parser   

        for ip in self.ip_to_port:
            if self.ip_to_port[ip] == self.path[-1]:
                dstip=ip
                dst=self.ip_to_mac[dstip]            

        for ip in self.ip_to_port:
            if self.ip_to_port[ip] == self.path[0]:
                srcip=ip
                src=self.ip_to_mac[srcip]
                
        for i in xrange(len(self.path) - 2, -1, -2):
            datapath_path = self.datapaths[self.path[i][0]]

            match1 = parser.OFPMatch(in_port=self.path[i][1], eth_src=src, eth_dst=dst, eth_type=0x0800,
                                    ipv4_src=srcip, ipv4_dst=dstip)
            self.delete_flow(datapath=datapath_path,match=match1)
            match2 = parser.OFPMatch(in_port=self.path[i+1][1], eth_src=dst, eth_dst=src, eth_type=0x0800,
                                    ipv4_src=dstip, ipv4_dst=srcip)
            self.delete_flow(datapath=datapath_path,match=match2)
```
* ` @set_ev_cls()`中的之前也讲过，是在说明何时调用该函数
* 前两个for循环是为了得到dst，src，dst_ip，src_ip，利用了全局变量`self.ip_to_port`和`self.ip_to_mac`
* 在第三个for循环中，从path的后面开始，将整条path全部删掉
* 这里的两个`parser.OFPMatch()`匹配了in port，dst，dst ip，src， src port，可以看出这个匹配得非常精细，但是实际上并不一定需要这么精细，在后面的讨论中应该会提到这个问题。（当时在写的时候在这里卡了很久很久。）
#### 2.4 结果展示
* 左为mininet，又为控制器，下为xterm h1
![result1](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E5%AE%9E%E9%AA%8C2%E6%89%93%E5%BC%80h1.jpg)
* 此时为在xterm中h1 ping h2的结果，可看到此时正在用最短路径
![result2](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E5%AE%9E%E9%AA%8C2down.jpg)
* 此时将s1 s4间的link断掉，可看出从原来的短路径换成了较长的路径
* 但是从黄色框框中可看出转换的时间略长，之后可能会去解决这个问题
![result3](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E5%AE%9E%E9%AA%8C2up.jpg)
* 此时将s1 s4间的link重新连接，可看出从原来的长路径又换成了较短的路径
### 3 负载均衡
#### 3.1 组表介绍
##### 3.1.1 组表构成
![group table](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E7%BB%84%E8%A1%A8.jpg)
* `Group Identifier`：一个32位无符号整数，Group Entry的唯一标识。 
* `Group Type`：决定了Group的语义，通俗地讲，就是表明了对数据包的处理行为，具体参考下文。 
* `Counters`：被该Group Entry处理过的数据包的统计量。 
* `Action Buckets`：一个Action Bucket的有序列表，每个Action Bucket又包含了一组Action集合及其参数
##### 3.1.2 组表类型
###### 【插入图片】
RyuBook无详细说明，详见[ryu中的组表](https://blog.csdn.net/haimianxiaojie/article/details/50994072)
* `OFPGT_ALL`all：Group Table中所有的Action Buckets都会被执行，这种类型的Group Table主要用于数据包的多播或者广播。数据包对于每一个Action Bucket都会被克隆一份，进而克隆体被处理。如果一个Action Bucket显示地将数据包发回其 ingress port，那么该数据包克隆体会被丢弃；但是，如果确实需要将数据包的一个克隆体发送回其 ingress port，那么该Group Table里就需要一个额外的Action Bucket，它包含了一个 output action 将数据包发送到 OFPP_IN_PORT Reserved Port。 
* `OFPGT_SELECT`select：仅仅执行Group Table中的某一个Action Bucket，基于OpenFlow Switch的调度算法，比如基于用户某个配置项的hash或者简单的round robin，所有的配置信息对于OpenFlow Switch来说都是属于外部的。当将数据包发往一个当前down掉的port时，Switch能将该数据包替代地发送给一个预留集合（能将数据包转发到当前live的ports上），而不是毫无顾忌地继续将数据包发送给这个down的port，这或许可以明显降低由于一个down的link或者switch带来的灾难。 
* `OFPGT_INDIRECT`indirect：执行Group Table中已经定义好的Action Bucket，这种类型的Group Table仅仅只支持一个Action Bucket。允许多个Flow Entries或者Groups 指向同一个通用的 Group Identifier，支持更快更高效的聚合。这种类型的Group Table与那些仅有一个Action Bucket的Group Table是一样的。 
* `OFPGT_FF`fast failover：执行第一个live的Action Bucket，每一个Action Bucket都关联了一个指定的port或者group来控制它的存活状态。Buckets会依照Group顺序依次被评估，并且第一个关联了一个live的port或者group的Action Bucket会被筛选出来。这种Group类型能够自行改变Switch的转发行为而不用事先请求Remote Controller。如果当前没有Buckets是live的，那么数据包就被丢弃，因此这种Group必须要实现一个管理存活状态的机制。
#### 3.2 思路
##### 3.2.1 获取从h1到h2的所有路径
* 可用DFS，或者就直接用前面算法中的最短路径最长路径也可以得到
```python
    def get_paths(self, src, dst):
        '''
        Get all paths from src to dst using DFS algorithm    
        '''
        if src == dst:
            # host target is on the same switch
            return [[src]]
        paths = []
        stack = [(src, [src])]
        while stack:
            (node, path) = stack.pop()
            for next in set(self.adjacency[node].keys()) - set(path):
                if next is dst:
                    paths.append(path + [next])
                else:
                    stack.append((next, path + [next]))
        print "Available paths from ", src, " to ", dst, " : ", paths
        return paths
```
* 这里为DFS算法，可得到多个路径放入paths
* `paths`:{[path1],[path2]}
##### 3.2.2 对路径上的每个switch，计算有几个出端口
```python
        for node in switches_in_paths:
        
            ports = defaultdict(list)

            for path in paths_with_ports:
                if node in path:
                    in_port = path[node][0]
                    out_port = path[node][1]
                    if (out_port, pw[i]) not in ports[in_port]:
                        ports[in_port].append((out_port, pw[i]))
                i += 1
                
                out_ports = ports[in_port]
```
* `paths_with_ports`:[{dpid1:(in_port,out_port),dpid2(in_port,out_port),...},{...},...]
##### 3.2.3 对于有两个及以上出端口的switch，添加组表
```python
                if len(out_ports) > 1:
                    group_id = None
                    group_new = False

                    buckets = []

                    for port, weight in out_ports:
                        bucket_weight = int(round((1 - weight/sum_of_pw) * 10))
                        bucket_action = [ofp_parser.OFPActionOutput(port)]
                        buckets.append(
                            ofp_parser.OFPBucket(
                                weight=bucket_weight,
                                watch_port=port,
                                watch_group=ofp.OFPG_ANY,
                                actions=bucket_action
                            )
                        )

                    if group_new:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_ADD, ofp.OFPGT_SELECT, group_id,
                            buckets
                        )
                        dp.send_msg(req)
                    else:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_MODIFY, ofp.OFPGT_SELECT,
                            group_id, buckets)
                        dp.send_msg(req)
```
* 对于有两个以上端口的switch，添加组表，对于只有一个出端口的，就只需要添加流表
* 这里weight的计算方法为找出所有路径的跳数，然后除以该路径的跳数，然后1减去得到的值，再乘以10，即可得到weight
这部分代码为`ryu_multipath.py`，详见[Multipath Routing with Load Balancing using RYU OpenFlow Controller](https://wildanmsyah.wordpress.com/2018/01/13/multipath-routing-with-load-balancing-using-ryu-openflow-controller/#more-556)
#### 3.3 代码`load_balance.py`
##### 3.3.1 整体情况
1. 通过之前的最短路径和最长路径算法，直接得到该拓扑的两条路径
2. 分析该拓扑，可知仅有switch1和switch5有两个出端口，因此直接对这两个switch添加组表
3. 添加组表时，以10-len(self.path)作为bucket weight，因为长度越短的weight应该越高，且最好比例差距大一些
4. group id可以为随机数
##### 3.3.2 部分代码
```python
    def send_group_mod(self, datapath,flag,):
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        buckets = []
        
        port_1 = 3
        port_2 = 2
        bucket_action_1 = [ofp_parser.OFPActionOutput(port_1)]
        bucket_action_2 = [ofp_parser.OFPActionOutput(port_2)]
        
        buckets = [
            ofp_parser.OFPBucket(3, port_1, ofproto.OFPG_ANY, bucket_action_1),
            ofp_parser.OFPBucket(2, port_2, ofproto.OFPG_ANY, bucket_action_2)]
        if flag == 1:
            group_id = 101
        elif flag == 5 :
            group_id = 105
        req = ofp_parser.OFPGroupMod(datapath, ofproto.OFPFC_ADD,
                                        ofproto.OFPGT_SELECT, group_id, buckets)

        datapath.send_msg(req)
```
![topo](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/topo_port.png)
* 根据拓扑结构可知，短路径的switch1和switch5的出端口都是3，而长路径的出端口都是2
* 短路径weight为3，长路径weight为2
* 通过flag确定目前是在为switch1还是switch5添加组表
#### 3.4 结果展示
##### 3.4.1 switch1 和 switch 5组表
![group table](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E7%BB%84%E8%A1%A8.png)
* 由图可见s1和s2的组表，s1的组表id为101，短路径的weight为3，出端口为3，长路径weight为2，出端口为2，s5组表id为105，其他与s1相似
##### 3.4.2 各个端口发送总数
###### 实验组：
![实验组](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E7%BB%93%E6%9E%9C.png)
* 左上为h1终端，中上为h2终端，右上为控制器，左下为mininet，右下为查看端口
* 分析右下s5的2端口和3端口，3端口为短路径，tx_pkts为发送的包数量，可见发送数量为409320,2端口为长路径，发包数量为97038，约为4:1的关系，可见满足了负载平衡
###### 对照组：
![对照组](https://github.com/minglii1998/EXPforSDN/blob/master/exp4/exp4/pic/%E5%AF%B9%E7%85%A7%E7%BB%84.png)
* 对照组为直接全部使用最短路径的方式发包
* 可见路径较短的3端口发送的包的数量490024，而长路径的2号端口仅有114，差了近5000倍
<br>
* 由此可得出结论，成功实现了负载均衡，将原来只用最短路径的5000:1平衡到了4:1

### 4. 总结
本次实验的总体难度还可以，在开始实验之前，我将助教提供的代码完整地研究了一遍，并做了完整的解析。<br><br>
在做动态改变转发规则时，我总结了4种获取最短路径的方法，在改变转发规则时，提供了2种判断转换的方法。因此对如何动态改变，以及如何使用hard timeout以及idle timeout都有了一个较明确的认识。<br><br>
在做链路故障恢复时，两个主要的函数`delete_flow()`和`get_OFPPortStatus_msg()`卡了比较久，对parser.OFPMatch()该匹配到什么程度一直不确定，最开始在写的时候没有写具体的匹配规则，因此再switch变更后，所有的流表，包括switch通向控制器的流表都会被删除，因此产生了很多麻烦。后来仿照add_flow()将匹配做到了最精细的情况，就解决了这个情况。但是至于该如何得到精确匹配需要的参数，也是卡了一段时间，最后发现可以直接使用前面定义的一些全局变量来获得，就不需要再自己来构造新的数据结构了。<br><br>
在负载均衡时，网上相关的资料比较少，但是好在找到了一两篇博客讲的比较详细，因此才能将组表的使用方法弄清楚。`load_balance.py`这个代码是完全基于现有的拓扑结构`topo.py`写的，但是可以看到上面的结果，负载均衡是可以成功实现的。后来试图写一个适用于所有拓扑结构的负载均衡代码`new_LB.py`，但是由于时间不够，还有不少需要debug。<br><br>
最后的快速链路故障恢复，也是用到组表的，需要将组表中的`OFPGT_SELECT`改为`OFPGT_FF`，但是经测试，恢复的时间似乎并没有比原来快太多，不知原因为何。<br><br>
总的来说，这次是我们的最后一次SDN的实验，通过这学期SDN的学习以及代码的编写，我觉得我对SDN有了还算比较清晰的认识，代码能力也有不小的提升。学了这么多SDN相关的东西，甚至希望今后还能用上。
