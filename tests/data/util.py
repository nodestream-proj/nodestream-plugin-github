import base64


def encode_as_node_id(s: str) -> str:
    return base64.standard_b64encode(s.encode("utf-8")).decode("utf-8")
