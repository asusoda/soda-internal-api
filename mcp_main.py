"""Run the MCP server (streamable HTTP on /mcp, port MCP_PORT or 8001).

Clients authenticate with a machine token: Authorization: Bearer plat_..., or get one with OAuth.
"""

import os
import socket
import struct
from pathlib import Path

import uvicorn

from core.config import config
from core.log import get_logger, init_sentry
from modules.dashboard import errors as error_alerts
from modules.manifest import load_tools
from modules.mcp.server import build_app

logger = get_logger(__name__)


def default_gateway(route_file: str = "/proc/net/route") -> str | None:
    """The IPv4 address of the default gateway, or None. In a container, the gateway is the host."""
    try:
        lines = Path(route_file).read_text().splitlines()[1:]
    except OSError:
        return None
    for line in lines:
        fields = line.split()
        # Destination 00000000 is the default route; flag 0x2 marks a gateway
        if len(fields) > 3 and fields[1] == "00000000" and int(fields[3], 16) & 0x2:
            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    return None


def forwarded_allow_ips(route_file: str = "/proc/net/route") -> str:
    """The addresses whose X-Forwarded-For uvicorn uses for the client IP.

    FORWARDED_ALLOW_IPS wins. Else this computer and the default gateway: the reverse proxy on the host
    reaches the container from the gateway address, and no other client can send from it. Never "*":
    uvicorn then takes the first X-Forwarded-For address, which the client sets.
    """
    if os.environ.get("FORWARDED_ALLOW_IPS"):
        return os.environ["FORWARDED_ALLOW_IPS"]
    gateway = default_gateway(route_file)
    return ",".join(["127.0.0.1", "::1", *([gateway] if gateway else [])])


def main() -> None:
    init_sentry(config.SENTRY, "mcp")
    error_alerts.setup("mcp")
    load_tools()
    port = int(os.environ.get("MCP_PORT", "8001"))
    proxies = forwarded_allow_ips()
    logger.info("Starting MCP server on port %s; X-Forwarded-For trusted from %s", port, proxies)
    uvicorn.run(
        build_app(),
        host="0.0.0.0",  # nosec B104 - the container binds all interfaces; compose publishes on 127.0.0.1
        port=port,
        log_level="info",
        forwarded_allow_ips=proxies,
    )


if __name__ == "__main__":
    main()
