EXP 3
====
###### 具体实验要求可从文件`SDN_exp3.pdf`中查看
### 1. P4语言介绍
#### 1.1 简介
   P4(Programming Protocol-Independent Packet Processors)是一种数据面的高级编程语言。他可以克服OpenFlow的局限。通过P4语言，我们可以定义我们想要的数据面。进而再通过南向协议添加流表项。<br><br>
   OpenFlow虽然为SDN奠定了基础。但是在进行应用开发的时候有一个很大的局限，就是OpenFlow没有真正做到协议不相关。也就是说，OpenFlow只能依据现有的协议来定义流表项。打个比方，就好像OpenFlow给了我们几个固定形状的积木，让我们自行组装，却不能让我们自己定义积木的形状。<br><br>
   通过P4，我们可以定义各种各样形状的积木，而通过南向协议，我们可以组装这些积木来实现特定的功能。也就是说，写好P4代码并不是全部，我们还需要写相应的控制面代码才能使网络正常工作。与OpenFlow对应的是P4 Runtime。为了实现协议无关。P4的设计者们还提供了一个南向协议——P4 runtime,与OpenFlow功能类似，但是P4 runtime可以充分利用P4协议无关的特性。
#### 1.2 组成
![组成](https://github.com/minglii1998/EXPforSDN/blob/master/exp3/exp3/pic/p4%E7%BB%84%E6%88%90.png)
* `Parser`: 解析器， 解析并且提取数据包头的各个字段。
* `Ingress`： Ingress处理，在这里定义Ingress流水线。
* `TM`： Traffic manager，有一些队列，用于流量控制（一些队列相关的metadata在此更新）。
* `Egress`： Egress, 在这里定义Egress流水线。
* `Deparser`：用于重组数据包，因为数据包在处理过程中经历了分解和处理。所以最后转发的时候需要重组一下
### 2. `simple_router-16.p4`代码解读
#### 2.1 Parser
* Parser包括Header和Parser两个部分
```p4
header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}
```
* header声明如上(以ethernet为例)，可以清楚地看到每个部分都是以bit作为单位
* 和C中的结构体类，定义完还需要下面的才可以成为实体
```p4
header ethernet_t ethernet;
```
or
```p4
struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}
```
* 若是在定义类时定义了多个header，则需要利用结构体
```p4
parser ParserImpl(packet_in packet, out headers hdr, inout metadata meta, inout standard_metadata_t standard_metadata) {

    state parse_ethernet {

        packet.extract(hdr.ethernet);

        transition select(hdr.ethernet.etherType) {
            16w0x800: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {

        packet.extract(hdr.ipv4);

        transition select(hdr.ipv4.protocol) {
            default: accept;
        }
    }

    state start {

        transition parse_ethernet;

    }
}
```
* parser中会有个`state start`
* 若`transition`后没有`select`，则运行到这里时进入下个state。eg，在`state start`后进入`state parse_ethernet`
* `extract`会将目前的packet以之前定义好的长度取出来。
* `select()`和C中的switch类似，根据括号中的内容判断下一步。eg，图中`state parse_ethernet`中，switch后若为16w0x800则进入`parse_ipv4`状态，否则直接结束（接受）
#### 2.2 Control
```p4
control ingress(inout headers hdr, inout metadata meta, inout standard_metadata_t standard_metadata) {

    action _drop() {
        mark_to_drop();
    }

    action set_dmac(bit<48> dmac) {
        hdr.ethernet.dstAddr = dmac;
    }

    action set_nhop(bit<32> nhop_ipv4, bit<9> port) {
        meta.routing_metadata.nhop_ipv4 = nhop_ipv4;
        standard_metadata.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl + 8w255;
    }

    table drop_all {
        actions = {
            _drop;
        }
        key = {
        }
        size = 1;
        default_action = _drop();
    }

    table forward {
        actions = {
            set_dmac;
            _drop;
        }

        key = {
            meta.routing_metadata.nhop_ipv4: exact;
        }
        size = 512;
    }

    table ipv4_lpm {
        actions = {
            set_nhop;
            _drop;
        }

        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        size = 1024;
        default_action = _drop();
    }

    apply {
        if (hdr.ipv4.isValid() && hdr.ipv4.ttl > 8w0) {
            ipv4_lpm.apply();
            forward.apply();
        }
        else {
            drop_all.apply();
        }
    }
}
```
* Control 最主要的目的是协调 Packet 要经过哪一些 Table
* p4里有两个主要的control flow，ingress和egress，分别代表packet的进入和离开
* `apply`意为将packet放入特定的table中运行。eg，上面apply中，若满足if条件则进入`ipv4_lpm`和`forward`table，否则进入`drop_all`table。
* `action`与C中的函数相似，定义了一些要做的动作，可以读取控制平面（control plane）提供的数据进行操作，然后根据action的代码内容影响数据平面（data plane）的工作。
* `table`义了匹配字段（key）、动作（action）和一些其他相关属性。先建立其匹配字段，然后数据包中去匹配table中的key中的字段，并获得要执行的"action"。
* `key`由一个个表单对组成（e:m），其中e是对应数据包中匹配的字段，而m是一个match_kind常数用来表示匹配的算法。eg，lpm 最长前缀字段，ternary 三元匹配
，exact 完全匹配
* `size`为table大小，`default_action`为当table miss的时候执行的动作
### 3. 实验1`exp3_tunnel.p4`
* 添加了⼀个名为mytunnel_t的新头部字段类型，其中包含两个16位字段：proto_id和dst_id。
```p4
header myTunnel_t {
    bit<16> proto_id;
    bit<16> dst_id;
}
```
* mytunnel头部需要添加到headers结构中。
```p4
struct headers {
    ethernet_t   ethernet;
    myTunnel_t   myTunnel;
    ipv4_t       ipv4;
}
```
* 更新解析器，根据Ethernet头部中的ethertype字段解析mytunnel头部或ipv4头部。与mytunnel头段对应的ethertype是0x1212。如果mytunnel的proto_id==type_ipv4（即0x0800），解析器还应在mytunnel头部之后解析ipv4头部。
```p4
    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_MYTUNNEL: parse_myTunnel;
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_myTunnel {
        packet.extract(hdr.myTunnel);
        transition select(hdr.myTunnel.proto_id) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }
```
* 定义⼀个名为mytunnel_forward的新的action，该动作只需将出⼝端⼝（即standard_metadata的egress_spec字段）设置为控制平⾯提供的端⼝号。
```p4
    action myTunnel_forward(egressSpec_t port) {
        standard_metadata.egress_spec = port;
    }
```
* 定义⼀个名为mytunnel_exact的新的table，该表根据mytunnel头部的dst_id字段执⾏精确匹配（exact）。如果表中存在匹配项，则此表应调⽤myTunnel_forward转发动作，否则应调⽤Drop动作。
```p4
    table myTunnel_exact {
        key = {
            hdr.myTunnel.dst_id: exact;
        }
        actions = {
            myTunnel_forward;
            drop;
        }
        size = 1024;
        default_action = drop();
    }
```
* 更新myIngress控制模块中的apply语句，使得在myTunnel头部有效的情况下应⽤新定义的mytunnel_exact表。否则，如果ipv4头部有效，则调⽤ipv4_lpm表。
```p4
    apply {
        if (hdr.ipv4.isValid() && !hdr.myTunnel.isValid()) {
            // Process only non-tunneled IPv4 packets
            ipv4_lpm.apply();
        }

        if (hdr.myTunnel.isValid()) {
            // process tunneled packets
            myTunnel_exact.apply();
        }
    }
}
```
* 更新deparser，由于头部的有效性是由隐集解析器提取，因此，这⾥不需要检查头部有效性
```p4
control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.myTunnel);
        packet.emit(hdr.ipv4);
    }
}
```
### 4. 实验2
#### 4.1 拓扑结构`mytopo.py`
```python
        switch1 = self.addSwitch('s1',sw_path = sw_path,json_path = json_path,thrift_port = 9090,pcap_dump = pcap_dump)
        switch2 = self.addSwitch('s2',sw_path = sw_path,json_path = json_path,thrift_port = 9091,pcap_dump = pcap_dump)
        switch3 = self.addSwitch('s3',sw_path = sw_path,json_path = json_path,thrift_port = 9092,pcap_dump = pcap_dump)

        host1 = self.addHost('h1',ip = "10.0.0.10/24", mac = '00:04:00:00:00:01')
        host2 = self.addHost('h2',ip = "10.0.1.10/24",mac = '00:04:00:00:00:02')
        host3 = self.addHost('h3',ip = "10.0.2.10/24",mac = '00:04:00:00:00:03')

        self.addLink(host1, switch1)
        self.addLink(host2, switch2)
        self.addLink(host3, switch3)
        self.addLink(switch1,switch2)
        self.addLink(switch2, switch3)
        self.addLink(switch3, switch1)
```
#### 4.2 流表命令`command1.txt`，`command2.txt`，`command3.txt`
```python
table_set_default ipv4_lpm drop
table_set_default myTunnel_exact drop
table_add ipv4_lpm ipv4_forward 10.0.0.10/32 => 00:04:00:00:00:01 1
table_add ipv4_lpm ipv4_forward 10.0.1.10/32 => 00:04:00:00:00:02 2
table_add ipv4_lpm ipv4_forward 10.0.2.10/32 => 00:04:00:00:00:03 3
table_add myTunnel_exact myTunnel_forward 1 => 1
table_add myTunnel_exact myTunnel_forward 2 => 2
table_add myTunnel_exact myTunnel_forward 3 => 3
```
* `table_set_default <table name> <action name> <action parameters>`:当table中的key不匹配的时候默认的action，这里的两个都是drop
* `table_add <table name> <action name> <match fields> => <action parameters> [priority]`:当matchfields匹配了，则按照表中的action执行
* eg`table_add ipv4_lpm ipv4_forward 10.0.0.10/32 => 00:04:00:00:00:01 1`意为若`ipv4_lpm`表中的key匹配了10.0.0.10/32，则把参数00:04:00:00:00:01传入，并调用`ipv4_forward`action
#### 4.3 运行结果
1. 运行拓扑
![1](https://github.com/minglii1998/EXPforSDN/blob/master/exp3/exp3/pic/%E8%BF%90%E8%A1%8C%E6%8B%93%E6%89%91.png)
2. 添加流表
![2](https://github.com/minglii1998/EXPforSDN/blob/master/exp3/exp3/pic/%E6%B7%BB%E5%8A%A0%E6%B5%81%E8%A1%A8.png)
3. 运行并抓包
![3](https://github.com/minglii1998/EXPforSDN/blob/master/exp3/exp3/pic/%E6%8A%93%E5%8C%85.png)
* 由wireshark抓包可见，有一type为0x1212的包，即为我们自己定义的

