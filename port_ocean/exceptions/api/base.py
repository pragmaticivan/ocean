import abc

from fastapi.responses import Response, PlainTextResponse
from port_ocean.exceptions.base import BaseOceanException


class BaseAPIException(BaseOceanException, abc.ABC):
    @abc.abstractmethod
    def response(self) -> Response:
        pass


class InternalServerException(BaseAPIException):
    def response(self) -> Response:
        return PlainTextResponse(content="Internal server error", status_code=500)
