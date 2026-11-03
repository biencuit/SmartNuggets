from mqtt_uplink import Outbox


def test_fifo_et_retrait(outbox: Outbox) -> None:
    first = outbox.enqueue("t/1", b"a")
    outbox.enqueue("t/2", b"b", retain=True)

    messages = outbox.peek()
    assert [(m.topic, m.payload, m.retain) for m in messages] == [
        ("t/1", b"a", False),
        ("t/2", b"b", True),
    ]
    outbox.remove(first)
    assert [m.topic for m in outbox.peek()] == ["t/2"]
    assert len(outbox) == 1


def test_messages_conserves_apres_redemarrage(tmp_path) -> None:
    path = str(tmp_path / "outbox.db")
    box = Outbox(path)
    box.enqueue("t", b"en attente")
    box.close()

    reopened = Outbox(path)
    assert [m.payload for m in reopened.peek()] == [b"en attente"]
    reopened.close()


def test_taille_maximale_supprime_les_plus_anciens(tmp_path) -> None:
    box = Outbox(str(tmp_path / "outbox.db"), max_messages=3)
    for i in range(5):
        box.enqueue("t", str(i).encode())
    assert [m.payload for m in box.peek()] == [b"2", b"3", b"4"]
    box.close()
