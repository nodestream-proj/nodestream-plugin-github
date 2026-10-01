from collections.abc import Mapping, Sequence

import httpx2

PrimitiveData = str | int | float | bool | None

URLTypes = httpx2.URL | str

type QueryParamTypes = (
    httpx2.QueryParams
    | Mapping[str, PrimitiveData | Sequence[PrimitiveData]]
    | list[tuple[str, PrimitiveData]]
    | tuple[tuple[str, PrimitiveData], ...]
)

type HeaderTypes = (
    httpx2.Headers
    | Mapping[str, str]
    | Mapping[bytes, bytes]
    | Sequence[tuple[str, str]]
    | Sequence[tuple[bytes, bytes]]
)
