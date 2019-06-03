EXP 3
====
###### 具体实验要求可从文件`SDN_exp3.pdf`中查看
### 1. P4语言介绍
#### 1.1 简介
   P4(Programming Protocol-Independent Packet Processors)是一种数据面的高级编程语言。他可以克服OpenFlow的局限。通过P4语言，我们可以定义我们想要的数据面。进而再通过南向协议添加流表项。<br><br>
   OpenFlow虽然为SDN奠定了基础。但是在进行应用开发的时候有一个很大的局限，就是OpenFlow没有真正做到协议不相关。也就是说，OpenFlow只能依据现有的协议来定义流表项。打个比方，就好像OpenFlow给了我们几个固定形状的积木，让我们自行组装，却不能让我们自己定义积木的形状。<br><br>
   通过P4，我们可以定义各种各样形状的积木，而通过南向协议，我们可以组装这些积木来实现特定的功能。也就是说，写好P4代码并不是全部，我们还需要写相应的控制面代码才能使网络正常工作。与OpenFlow对应的是P4 Runtime。为了实现协议无关。P4的设计者们还提供了一个南向协议——P4 runtime,与OpenFlow功能类似，但是P4 runtime可以充分利用P4协议无关的特性。
#### 1.2 组成
#### 【此处插入图片】
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
* 
