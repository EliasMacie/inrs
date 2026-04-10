from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.node import Controller
from mininet.cli import CLI

def run():
    topo = SingleSwitchTopo(k=3)
    net = Mininet(topo=topo, controller=Controller)
    
    net.start()

    h1, h2, h3 = net.get('h1', 'h2', 'h3')

    print("Teste inicial:")
    net.pingAll()

    print("Bloqueando comunicação entre h1 e h2...")
    net.get('s1').cmd(
        'ovs-ofctl add-flow s1 priority=100,ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=drop'
    )

    print("Teste após bloqueio:")
    h1.cmd('ping -c 3 10.0.0.2')

    print("Permitindo novamente...")
    net.get('s1').cmd('ovs-ofctl del-flows s1')

    net.pingAll()

    CLI(net)
    net.stop()

if __name__ == '__main__':
    run()