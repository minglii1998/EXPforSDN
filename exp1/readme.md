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
### 注意：
* add_flow()函数：将流表加入交换机<br>    match:这个交换机的match条件<br>    inst:match之后将执行的动作    
table:规则要放在哪个table中    
新增规则时，由controller(ryu)通过传送OFPFlowMod给switch
* dp_send_msg(mod):对switch新增规则    dp_send_msg(out):告诉switch执行的动作
* 运行顺序：
    在ryu打开后，打开mn，立刻进入switch_features_handler()，会执行一次add_flow。在ping的过程中会不停进入packet_handler()，
    并add_flow
* match=Parser.OFPMatch()：产生match条件，若括号中无任何条件，则表示所有封包都会match此规则。
* def switch_features_handler(self, ev):这个基本属于固定写法，是在switch和controller连接时，对table加入规则，
    数据包会直接送入controller，并触发packet_in事件
    
###### 这是除了`SDN_exp1.pdf`文件以外遇到的一些坑，或者值得记录的地方，其实还有很多，但是不想写了.先这样吧。
