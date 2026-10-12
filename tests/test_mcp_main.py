"""The addresses that the MCP server trusts for X-Forwarded-For."""

import mcp_main

ROUTES = (
    "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    "eth0\t00000000\t0100590A\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
    "eth0\t0000590A\t00000000\t0001\t0\t0\t0\t00FFFFFF\t0\t0\t0\n"
)


def test_the_gateway_is_trusted(tmp_path, monkeypatch):
    routes = tmp_path / "route"
    routes.write_text(ROUTES)
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    assert mcp_main.default_gateway(str(routes)) == "10.89.0.1"
    assert mcp_main.forwarded_allow_ips(str(routes)) == "127.0.0.1,::1,10.89.0.1"


def test_no_route_file_trusts_only_this_computer(tmp_path, monkeypatch):
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    assert mcp_main.forwarded_allow_ips(str(tmp_path / "missing")) == "127.0.0.1,::1"


def test_the_setting_wins(tmp_path, monkeypatch):
    routes = tmp_path / "route"
    routes.write_text(ROUTES)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.88.0.1")
    assert mcp_main.forwarded_allow_ips(str(routes)) == "10.88.0.1"
