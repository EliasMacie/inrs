# from mininet.net import Mininet
# from mininet.topo import SingleSwitchTopo
# from mininet.node import Controller
# from mininet.cli import CLI

# def run():
#     topo = SingleSwitchTopo(k=3)
#     net = Mininet(topo=topo, controller=Controller)
    
#     net.start()

#     h1, h2, h3 = net.get('h1', 'h2', 'h3')

#     print("Teste inicial:")
#     net.pingAll()

#     print("Bloqueando comunicação entre h1 e h2...")
#     net.get('s1').cmd(
#         'sh ovs-ofctl add-flow s1 priority=100,ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=drop'
#     )

#     print("Teste após bloqueio:")
#     net.pingAll()

#     print("Permitindo novamente...")
#     net.get('s1').cmd('ovs-ofctl del-flows s1')

#     net.pingAll()

#     CLI(net)
#     net.stop()

# if __name__ == '__main__':
#     run()


#!/usr/bin/env python3
"""
====================================================================
  TRABALHO PRÁTICO — REDES SDN com Mininet
  Disciplina: Redes de Computadores / SDN
====================================================================
  Topologia: 3 hosts (H1, H2, H3) + 1 switch OpenFlow (OvS)
  Controlador: SimpleSwitch (Ryu ou controlador padrão)
  Funcionalidades:
    - Conectividade básica (ping)
    - Criação manual de flow entries via ovs-ofctl
    - Bloqueio/permissão de comunicação entre hosts
    - Modificação dinâmica de regras de fluxo
====================================================================
  Pré-requisitos:
    sudo apt-get install mininet openvswitch-switch python3-pip
    pip3 install ryu   (opcional, para o controlador Ryu)
  Execução:
    sudo python3 sdn_mininet.py
====================================================================
"""

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time
import subprocess
import sys

# ─────────────────────────────────────────────
#  PARÂMETROS GLOBAIS
# ─────────────────────────────────────────────
SWITCH_NAME = "s1"
HOSTS       = ["h1", "h2", "h3"]
OPENFLOW_V  = "OpenFlow13"   # versão do protocolo OpenFlow

# ─────────────────────────────────────────────
#  1. CRIAR TOPOLOGIA
# ─────────────────────────────────────────────
def criar_topologia():
    """
    Cria a topologia:
        H1 ──┐
        H2 ──┤── Switch S1 (OvS)
        H3 ──┘
    """
    info("\n=== [1/4] A criar topologia SDN ===\n")

    # Instancia a rede com controlador padrão do Mininet
    net = Mininet(
        controller=Controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True     # MAC determinístico: 00:00:00:00:00:01, etc.
    )

    # Controlador
    info("  + Adicionando controlador...\n")
    c0 = net.addController("c0")

    # Switch OpenFlow
    info("  + Adicionando switch OvS...\n")
    s1 = net.addSwitch(SWITCH_NAME, protocols=OPENFLOW_V)

    # Hosts com IPs estáticos
    info("  + Adicionando hosts H1, H2, H3...\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2 = net.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3 = net.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")

    # Ligações (com limitação de largura de banda para simular rede real)
    info("  + Criando ligações (100 Mbps)...\n")
    net.addLink(h1, s1, bw=100)
    net.addLink(h2, s1, bw=100)
    net.addLink(h3, s1, bw=100)

    return net, c0, s1, h1, h2, h3


# ─────────────────────────────────────────────
#  2. CONFIGURAR O SWITCH OPENFLOW
# ─────────────────────────────────────────────
def configurar_switch_openflow(net):
    """
    Configura o switch para usar OpenFlow 1.3.
    Adiciona flow entries básicas para encaminhamento L2.
    """
    info("\n=== [2/4] A configurar regras OpenFlow ===\n")
    s1 = net.get(SWITCH_NAME)

    # Define versão do protocolo
    s1.cmd(f"ovs-vsctl set bridge {SWITCH_NAME} protocols={OPENFLOW_V}")

    # Aguarda estabilização do switch
    time.sleep(1)

    # ── FLOW 1: H1 → H2 (encaminhamento MAC)
    info("  + Flow: H1 (00:01) → H2 (00:02) via porta 2\n")
    s1.cmd(
        f"ovs-ofctl -O {OPENFLOW_V} add-flow {SWITCH_NAME} "
        "priority=100,dl_dst=00:00:00:00:00:02,actions=output:2"
    )

    # ── FLOW 2: H2 → H1 (reverso)
    info("  + Flow: H2 (00:02) → H1 (00:01) via porta 1\n")
    s1.cmd(
        f"ovs-ofctl -O {OPENFLOW_V} add-flow {SWITCH_NAME} "
        "priority=100,dl_dst=00:00:00:00:00:01,actions=output:1"
    )

    # ── FLOW 3: H3 → qualquer host (flood)
    info("  + Flow: H3 (00:03) → broadcast/flood via porta 3\n")
    s1.cmd(
        f"ovs-ofctl -O {OPENFLOW_V} add-flow {SWITCH_NAME} "
        "priority=100,dl_dst=00:00:00:00:00:03,actions=output:3"
    )

    # ── FLOW 4: tráfego ARP — flood para todos os portos
    info("  + Flow: ARP → FLOOD (necessário para resolução de endereços)\n")
    s1.cmd(
        f"ovs-ofctl -O {OPENFLOW_V} add-flow {SWITCH_NAME} "
        "priority=200,dl_type=0x0806,actions=FLOOD"
    )


# ─────────────────────────────────────────────
#  3. TESTAR CONECTIVIDADE
# ─────────────────────────────────────────────
def testar_conectividade(net):
    """
    Testa ping entre todos os hosts e exibe resultados.
    """
    info("\n=== [3/4] Teste de conectividade (ping) ===\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    h3 = net.get("h3")

    resultados = {}

    info("  Ping H1 → H2 ...\n")
    r = h1.cmd("ping -c 3 -W 1 10.0.0.2")
    resultados["H1→H2"] = "OK ✓" if "0% packet loss" in r else "FALHOU ✗"
    info(f"  Resultado: {resultados['H1→H2']}\n")

    info("  Ping H1 → H3 ...\n")
    r = h1.cmd("ping -c 3 -W 1 10.0.0.3")
    resultados["H1→H3"] = "OK ✓" if "0% packet loss" in r else "FALHOU ✗"
    info(f"  Resultado: {resultados['H1→H3']}\n")

    info("  Ping H2 → H3 ...\n")
    r = h2.cmd("ping -c 3 -W 1 10.0.0.3")
    resultados["H2→H3"] = "OK ✓" if "0% packet loss" in r else "FALHOU ✗"
    info(f"  Resultado: {resultados['H2→H3']}\n")

    info("\n  ── Resumo dos testes de ping ──\n")
    for par, res in resultados.items():
        info(f"     {par}: {res}\n")

    return resultados


# ─────────────────────────────────────────────
#  4. CONTROLO DINÂMICO DE FLUXOS (SCRIPT)
# ─────────────────────────────────────────────
def bloquear_comunicacao(net, host_origem, host_destino, ip_dst):
    """
    Bloqueia a comunicação entre dois hosts adicionando
    uma flow entry com ação DROP (prioridade alta).

    Exemplo: bloquear_comunicacao(net, "h1", "h2", "10.0.0.2")
    """
    info(f"\n  [BLOQUEAR] {host_origem} → {host_destino} ({ip_dst})\n")
    s1 = net.get(SWITCH_NAME)
    src = net.get(host_origem)

    # Flow DROP com prioridade 500 (sobrepõe flows de encaminhamento)
    s1.cmd(
        f"ovs-ofctl -O {OPENFLOW_V} add-flow {SWITCH_NAME} "
        f"priority=500,ip,nw_dst={ip_dst},actions=drop"
    )
    info(f"  → Flow DROP instalado: qualquer pacote IP para {ip_dst} será descartado\n")

    # Verificação imediata
    r = src.cmd(f"ping -c 2 -W 1 {ip_dst}")
    status = "BLOQUEADO ✓" if "100% packet loss" in r else "ainda a passar (?)"
    info(f"  → Verificação ping: {status}\n")


def permitir_comunicacao(net, host_origem, host_destino, ip_dst):
    """
    Remove o bloqueio e restaura a comunicação entre dois hosts.
    """
    info(f"\n  [PERMITIR] {host_origem} → {host_destino} ({ip_dst})\n")
    s1 = net.get(SWITCH_NAME)
    src = net.get(host_origem)

    # Remove o flow DROP específico
    s1.cmd(
        f"ovs-ofctl -O {OPENFLOW_V} del-flows {SWITCH_NAME} "
        f"ip,nw_dst={ip_dst}"
    )
    info(f"  → Flow DROP removido para {ip_dst}\n")

    time.sleep(0.5)
    r = src.cmd(f"ping -c 2 -W 1 {ip_dst}")
    status = "RESTAURADO ✓" if "0% packet loss" in r else "ainda bloqueado (?)"
    info(f"  → Verificação ping: {status}\n")


def modificar_fluxo_dinamico(net):
    """
    Demonstração de rede programável:
    Altera dinamicamente o comportamento da rede sem reconfigurar hardware.
    
    Cenário:
      1. H1 consegue chegar a H2 (normal)
      2. Bloqueamos H1 → H2
      3. Mostramos que H1 NÃO consegue chegar a H2
      4. Desbloqueamos
      5. Mostramos que H1 VOLTA a conseguir chegar a H2
    """
    info("\n=== [4/4] Demonstração de rede programável ===\n")
    info("  Cenário: bloquear e restaurar comunicação H1 ↔ H2\n")

    h1 = net.get("h1")
    h2 = net.get("h2")

    # Estado inicial
    info("\n  [Estado 1] Antes do bloqueio:\n")
    r = h1.cmd("ping -c 2 -W 1 10.0.0.2")
    info(f"  H1→H2: {'CONECTADO' if '0% packet loss' in r else 'sem resposta'}\n")

    # Bloqueia
    time.sleep(1)
    bloquear_comunicacao(net, "h1", "h2", "10.0.0.2")

    # Estado após bloqueio
    info("\n  [Estado 2] Após instalação do DROP flow:\n")
    r = h1.cmd("ping -c 2 -W 1 10.0.0.2")
    info(f"  H1→H2: {'BLOQUEADO ✓' if '100% packet loss' in r else 'ainda a passar'}\n")

    # Aguarda 3 segundos para demonstração
    info("\n  ... aguardando 3 segundos (simular monitorização) ...\n")
    time.sleep(3)

    # Desbloqueia
    permitir_comunicacao(net, "h1", "h2", "10.0.0.2")

    # Estado final
    info("\n  [Estado 3] Após remoção do DROP flow (restaurado):\n")
    r = h1.cmd("ping -c 2 -W 1 10.0.0.2")
    info(f"  H1→H2: {'RESTAURADO ✓' if '0% packet loss' in r else 'ainda bloqueado'}\n")


def mostrar_flow_table(net):
    """
    Exibe a flow table atual do switch OvS.
    Útil para visualizar as regras de encaminhamento ativas.
    """
    info("\n  ── Flow Table Atual (s1) ──\n")
    s1 = net.get(SWITCH_NAME)
    flows = s1.cmd(f"ovs-ofctl -O {OPENFLOW_V} dump-flows {SWITCH_NAME}")
    info(flows + "\n")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    setLogLevel("info")

    info("""
╔══════════════════════════════════════════════════════╗
║     TRABALHO PRÁTICO SDN — Mininet + OpenFlow        ║
║     Topologia: 3 hosts + 1 switch OvS               ║
╚══════════════════════════════════════════════════════╝
""")

    # 1. Criar e iniciar rede
    net, c0, s1, h1, h2, h3 = criar_topologia()
    net.start()

    # 2. Configurar flows OpenFlow
    configurar_switch_openflow(net)

    # 3. Testar conectividade inicial
    testar_conectividade(net)

    # 4. Mostrar flow table
    mostrar_flow_table(net)

    # 5. Demonstração de rede programável
    modificar_fluxo_dinamico(net)

    # 6. Mostrar flow table final
    info("\n  ── Flow Table Final ──\n")
    mostrar_flow_table(net)

    # 7. Abrir CLI interativa para exploração manual
    info("\n=== CLI Mininet disponível. Comandos úteis: ===\n")
    info("  pingall            — testa todos os pares\n")
    info("  h1 ping h2         — ping de h1 para h2\n")
    info("  sh ovs-ofctl -O OpenFlow13 dump-flows s1  — ver flows\n")
    info("  exit               — terminar\n\n")
    CLI(net)

    # Cleanup
    net.stop()
    info("\n  Rede terminada. Limpando recursos...\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        sys.exit(0)
    main()
