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




