EXP 4
====
###### 具体实验要求可从文件`SDN_exp4.pdf`中查看
### 0. 环境与拓扑结构
环境与第一次第二次实验相同，拓扑结构如图：
##### 【需在这里加图】
### 1. 链路恢复
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
3. 需要一个变量来判断目前的询问是第几次，并判断究竟该install长路径还是短路径（3种方法）
   1. 利用系统时间<br>
   交换机在获得流表后，就不会再向控制器询问，直到5秒后交换机流表被删除，此时才会再次向控制器询问<br>
   因此可以每次在install_path时都获得一下当前时间，跟上一次的时间对比，若有一定长度，如超过3秒，就可以认为此时应该转换mod<br>
   每次超过3秒都会counting+1，然后取模counting判断mod
   2. 利用install_flow的次数<br>
   交换机在每次请求时，所需要install path的次数是固定的，因此可记录其次数，然后通过取模判断mod
   3. 直接在每次install时翻转mod(最简单)
#### 1.3 代码实现
##### 获取最长路径：方法1
```python
    def long_path(self, src, dst, bw=0):
    ...
        w = -1  # weight
    ...
```
* 就只改了只加了一个负号，贼没牌面
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
        
