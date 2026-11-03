import pytest

from app.mqtt import topics
from app.mqtt.messages import parse_status


def test_topic_et_abonnement() -> None:
    assert topics.topic("coop_01", topics.Channel.COMMANDS) == "smartnuggets/coop_01/commands"
    assert topics.subscription(topics.Channel.TELEMETRY) == "smartnuggets/+/telemetry"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("smartnuggets/coop_01/telemetry", ("coop_01", topics.Channel.TELEMETRY)),
        ("smartnuggets/coop_01/status", ("coop_01", topics.Channel.STATUS)),
        ("smartnuggets/coop_01/inconnu", None),
        ("autre/coop_01/telemetry", None),
        ("smartnuggets/../telemetry", None),
        ("smartnuggets/coop_01/telemetry/extra", None),
    ],
)
def test_parse(value: str, expected: tuple[str, topics.Channel] | None) -> None:
    assert topics.parse(value) == expected


def test_parse_status() -> None:
    assert parse_status(b"online") is True
    assert parse_status(b" OFFLINE\n") is False
    assert parse_status(b"???") is None
