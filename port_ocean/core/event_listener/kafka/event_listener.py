import threading
from typing import Any, Callable, Literal

from loguru import logger
from pydantic import Field

from port_ocean.consumers.kafka_consumer import KafkaConsumer, KafkaConsumerConfig
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)


class KafkaEventListenerSettings(EventListenerSettings):
    type: Literal["KAFKA"]
    brokers: str = ""
    security_protocol: str = Field(alias="securityProtocol", default="SASL_SSL")
    authentication_mechanism: str = Field(
        alias="authenticationMechanism", default="SCRAM-SHA-512"
    )
    kafka_security_enabled: bool = Field(alias="kafkaSecurityEnabled", default=True)
    consumer_poll_timeout: int = Field(alias="consumerPollTimeout", default=1)


class KafkaEventListener(BaseEventListener):
    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: KafkaEventListenerSettings,
        org_id: str,
        integration_identifier: str,
        integration_type: str,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config
        self.org_id = org_id
        self.integration_identifier = integration_identifier
        self.integration_type = integration_type

    async def _get_kafka_config(self) -> KafkaConsumerConfig:
        if self.event_listener_config.kafka_security_enabled:
            creds = await ocean.port_client.get_kafka_creds()
            return KafkaConsumerConfig(
                **self.event_listener_config.dict(),
                username=creds.get("username"),
                password=creds.get("password"),
                group_name=f"{self.integration_type}.{self.integration_identifier}",
            )

        return KafkaConsumerConfig.parse_obj(self.event_listener_config.dict())

    def should_be_processed(self, msg_value: dict[Any, Any], topic: str) -> bool:
        if "change.log" in topic:
            return msg_value.get("changelogDestination", {}).get("type", "") == "KAFKA"

        return False

    async def _handle_message(self, message: dict[Any, Any], topic: str) -> None:
        if not self.should_be_processed(message, topic):
            return

        if "change.log" in topic:
            await self.events["on_resync"](message)

    def wrapped_start(
        self, context: PortOceanContext, func: Callable[[], None]
    ) -> Callable[[], None]:
        ocean_app = context.app

        def wrapper() -> None:
            initialize_port_ocean_context(ocean_app=ocean_app)
            func()

        return wrapper

    async def start(self) -> None:
        consumer = KafkaConsumer(
            msg_process=self._handle_message,
            config=await self._get_kafka_config(),
            org_id=self.org_id,
        )
        logger.info("Starting Kafka consumer")
        threading.Thread(
            name="ocean_kafka_consumer",
            target=self.wrapped_start(ocean, consumer.start),
        ).start()