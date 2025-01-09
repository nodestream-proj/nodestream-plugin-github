from collections.abc import Mapping, Sequence

from httpx import Headers, QueryParams

PrimitiveData = str | int | float | bool | None

QueryParamTypes = (
    QueryParams
    | Mapping[str, PrimitiveData | Sequence[PrimitiveData]]
    | list[tuple[str, PrimitiveData]]
    | tuple[tuple[str, PrimitiveData], ...]
    | str
    | bytes
)
HeaderTypes = (
    Headers
    | Mapping[str, str]
    | Mapping[bytes, bytes]
    | Sequence[tuple[str, str]]
    | Sequence[tuple[bytes, bytes]]
)
