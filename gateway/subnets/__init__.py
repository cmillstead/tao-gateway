from gateway.subnets.base import BaseAdapter
from gateway.subnets.sn1_text import SN1TextAdapter
from gateway.subnets.sn19_image import SN19ImageAdapter
from gateway.subnets.sn62_code import SN62CodeAdapter

# Config-driven adapter definitions.
# To add a new subnet: create adapter file, add settings, add one tuple here.
# Format: (AdapterClass, model_names, netuid_setting_name)
ADAPTER_DEFINITIONS: list[tuple[type[BaseAdapter], list[str], str]] = [
    (SN1TextAdapter, ["tao-sn1"], "sn1_netuid"),
    (SN19ImageAdapter, ["tao-sn19"], "sn19_netuid"),
    (SN62CodeAdapter, ["tao-sn62"], "sn62_netuid"),
]

# Re-export factory for lifespan use
from gateway.subnets.factory import adapter_factory, get_model_names  # noqa: E402, F401
