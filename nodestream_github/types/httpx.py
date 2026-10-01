from collections.abc import Mapping, Sequence

import httpx

PrimitiveData = str | int | float | bool | None

type QueryParamTypes = (
    httpx.QueryParams
    | Mapping[str, PrimitiveData | Sequence[PrimitiveData]]
    | list[tuple[str, PrimitiveData]]
    | tuple[tuple[str, PrimitiveData], ...]
    | str
    | bytes
)
type HeaderTypes = (
    httpx.Headers
    | Mapping[str, str]
    | Mapping[bytes, bytes]
    | Sequence[tuple[str, str]]
    | Sequence[tuple[bytes, bytes]]
)
