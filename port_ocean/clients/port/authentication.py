from datetime import datetime
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

from port_ocean.clients.port.types import UserAgentType


class TokenResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    expires_in: int = Field(alias="expiresIn")
    token_type: str = Field(alias="tokenType")
    _retrieved_time: datetime = PrivateAttr(datetime.now())

    @property
    def expired(self) -> bool:
        return (
            self._retrieved_time.timestamp() + self.expires_in
            < datetime.now().timestamp()
        )

    @property
    def full_token(self) -> str:
        return f"{self.token_type} {self.access_token}"


class PortAuthentication:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        api_url: str,
        integration_identifier: str,
        integration_type: str,
    ):
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.integration_identifier = integration_type
        self.integration_type = integration_identifier
        self._last_token_object: TokenResponse | None = None

    async def _get_token(self, client_id: str, client_secret: str) -> TokenResponse:
        async with httpx.AsyncClient() as client:
            logger.info(f"Fetching access token for clientId: {client_id}")

            credentials = {"clientId": client_id, "clientSecret": client_secret}
            token_response = await client.post(
                f"{self.api_url}/auth/access_token", json=credentials
            )
            token_response.raise_for_status()
            return TokenResponse(**token_response.json())

    def user_agent(self, user_agent_type: UserAgentType | None = None) -> str:
        user_agent = f"port-ocean/{self.integration_type}/{self.integration_identifier}"
        if user_agent_type:
            user_agent += f"/{user_agent_type.value or UserAgentType.exporter.value}"

        return user_agent

    async def headers(
        self, user_agent_type: UserAgentType | None = None
    ) -> dict[Any, Any]:
        return {
            "Authorization": await self.token,
            "User-Agent": self.user_agent(user_agent_type),
        }

    @property
    async def token(self) -> str:
        if not self._last_token_object or self._last_token_object.expired:
            self._last_token_object = await self._get_token(
                self.client_id, self.client_secret
            )

        return self._last_token_object.full_token