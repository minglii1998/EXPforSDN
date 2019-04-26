from mininet.topo import Topo

class MyTopo( Topo ):

    def build( self ):
        "Create custom topo."

        # Add hosts and switches
        s1= self.addSwitch( 's1' )
        s2= self.addSwitch( 's2' )
        s3= self.addSwitch( 's3' )
        s4= self.addSwitch( 's4' )
        s5= self.addSwitch( 's5' )
        s6= self.addSwitch( 's6' )
        s7= self.addSwitch( 's7' )
        s8= self.addSwitch( 's8' )
        s9= self.addSwitch( 's9' )
        s10= self.addSwitch( 's10' )
        s11= self.addSwitch( 's11' )
        s12= self.addSwitch( 's12' )
        s13= self.addSwitch( 's13' )
        s14= self.addSwitch( 's14' )

        # Add links
        self.addLink( s1, s2 )
        self.addLink( s2, s3 )
        self.addLink( s2, s4 )
        self.addLink( s2, s5 )
        self.addLink( s2, s8 )
        self.addLink( s2, s6 )
        self.addLink( s7, s8 )
        self.addLink( s8, s9 )
        self.addLink( s9, s10 )
        self.addLink( s10, s11 )
        self.addLink( s10, s12 )
        self.addLink( s10, s13 )
        self.addLink( s14, s13 )


topos = { 'mytopo': ( lambda: MyTopo() ) }