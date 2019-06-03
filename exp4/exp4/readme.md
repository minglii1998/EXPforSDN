EXP 4
====
###### 具体实验要求可从文件`SDN_exp4.pdf`中查看
### 0. 环境与拓扑结构
环境与第一次第二次实验相同，拓扑结构如图：
##### 【需在这里加图】
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
##### 【需在这里加图】
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
左为mininet，又为控制器，下为xterm h1
##### 【需在这里加图】
此时为在xterm中h1 ping h2的结果，可看到此时正在用最短路径
##### 【需在这里加图】
此时将s1 s4间的link断掉，可看出从原来的短路径换成了较长的路径<br>
但是从黄色框框中可看出转换的时间略长，之后可能会去解决这个问题
##### 【需在这里加图】
此时将s1 s4间的link重新连接，可看出从原来的长路径又换成了较短的路径
#### 2.5 遇到的问题
#### 2.6 方法改进
### 3 总结
###### 各文档解释：
