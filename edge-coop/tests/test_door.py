"""Mécanique de la porte, comptage des passages et plage horaire."""

from datetime import datetime

import pytest

from door_controller import (
    Door,
    DoorConfig,
    DoorState,
    MoveResult,
    Passage,
    PassageCounter,
    Schedule,
    Source,
)
from hardware.mock import FakeStepper, FakeSwitch, LimitSwitch

CONFIG = DoorConfig(travel_steps=100, margin_steps=20, check_every=10)


def make_door(**kwargs):
    motor = FakeStepper()
    changes: list[tuple[DoorState, Source]] = []
    door = Door(
        motor,
        CONFIG,
        on_change=lambda state, source: changes.append((state, source)),
        **kwargs,
    )
    return door, motor, changes


# ---------------------------------------------------------------------- porte


def test_ouverture_puis_fermeture_sans_fin_de_course():
    door, motor, changes = make_door()
    assert door.open(Source.MANUAL_APP) == MoveResult.DONE
    assert door.state == DoorState.OPEN and motor.position == 100
    assert door.close(Source.SCHEDULE) == MoveResult.DONE
    assert door.state == DoorState.CLOSED and motor.position == 0
    assert changes == [
        (DoorState.OPENING, Source.MANUAL_APP),
        (DoorState.OPEN, Source.MANUAL_APP),
        (DoorState.CLOSING, Source.SCHEDULE),
        (DoorState.CLOSED, Source.SCHEDULE),
    ]


def test_bobines_coupees_apres_chaque_mouvement():
    door, motor, _ = make_door()
    door.open(Source.MANUAL_APP)
    assert not motor.energized


def test_deja_dans_le_bon_etat():
    door, motor, changes = make_door()
    assert door.close(Source.MANUAL_APP) == MoveResult.ALREADY
    assert motor.steps == 0 and changes == []


def test_les_fins_de_course_arretent_le_moteur():
    motor = FakeStepper()
    door = Door(
        motor,
        CONFIG,
        top=LimitSwitch(motor, 90, above=True),
        bottom=LimitSwitch(motor, 0, above=False),
    )
    door.open(Source.AI_AUTO)
    assert motor.position == 90  # arrêté par le fin de course, avant les 100 pas


def test_fin_de_course_jamais_atteint_porte_bloquee():
    motor = FakeStepper()
    top = LimitSwitch(motor, 100, above=True)
    top.stuck = True
    door = Door(motor, CONFIG, top=top)
    assert door.open(Source.MANUAL_APP) == MoveResult.BLOCKED
    assert door.state == DoorState.ERROR
    assert motor.steps == 120  # course + marge, puis abandon
    assert not motor.energized


def test_obstacle_pendant_la_fermeture_la_porte_remonte():
    obstacle = FakeSwitch()
    door, motor, changes = make_door(obstacle=obstacle, initial=DoorState.OPEN)
    motor.position = 100

    def step_and_block(direction, original=motor.step):
        original(direction)
        if motor.position == 60:
            obstacle.active = True

    motor.step = step_and_block
    assert door.close(Source.SCHEDULE) == MoveResult.OBSTACLE
    assert door.state == DoorState.OPEN
    assert motor.position == 100
    assert changes[-2:] == [(DoorState.OPENING, Source.FAILSAFE), (DoorState.OPEN, Source.FAILSAFE)]


def test_fermeture_refusee_sans_bouger_si_un_obstacle_est_deja_la():
    door, motor, changes = make_door(obstacle=FakeSwitch(active=True), initial=DoorState.OPEN)
    assert door.close(Source.SCHEDULE) == MoveResult.OBSTACLE
    assert door.state == DoorState.OPEN
    assert motor.steps == 0 and changes == []


def test_obstacle_qui_disparait_la_fermeture_reussit():
    obstacle = FakeSwitch(active=True)
    door, motor, _ = make_door(obstacle=obstacle, initial=DoorState.OPEN)
    assert door.close(Source.SCHEDULE) == MoveResult.OBSTACLE
    obstacle.active = False
    assert door.close(Source.SCHEDULE) == MoveResult.DONE
    assert door.state == DoorState.CLOSED and motor.position == -100


def test_calibrage_au_demarrage_descend_jusqu_au_fin_de_course_bas():
    motor = FakeStepper()
    motor.position = 37  # porte à mi-hauteur après une coupure de courant
    door = Door(motor, CONFIG, bottom=LimitSwitch(motor, 0, above=False))
    assert door.calibrate() == MoveResult.DONE
    assert door.state == DoorState.CLOSED and motor.position == 0


# ---------------------------------------------------------------------- comptage


def passe(counter, *etapes):
    """Rejoue une suite d'états (extérieure, intérieure) des barrières."""
    results = [counter.update(outer, inner) for outer, inner in etapes]
    return [r for r in results if r is not None]


ENTREE = [(True, False), (True, True), (False, True), (False, False)]
SORTIE = [(False, True), (True, True), (True, False), (False, False)]


def test_entree_et_sortie():
    seen: list[tuple[Passage, int]] = []
    counter = PassageCounter(5, on_passage=lambda p, n: seen.append((p, n)))
    assert passe(counter, *ENTREE) == [Passage.ENTRY]
    assert passe(counter, *SORTIE) == [Passage.EXIT]
    assert seen == [(Passage.ENTRY, 6), (Passage.EXIT, 5)]


@pytest.mark.parametrize(
    "etapes",
    [
        [(True, False), (False, False)],  # tête passée puis demi-tour
        [(True, False), (True, True), (True, False), (False, False)],  # demi-tour au milieu
        [(False, True), (False, False)],
    ],
)
def test_demi_tour_pas_compte(etapes):
    counter = PassageCounter(3)
    assert passe(counter, *etapes) == []
    assert counter.inside == 3


def test_le_compteur_ne_descend_pas_sous_zero_et_peut_etre_corrige():
    counter = PassageCounter(0)
    passe(counter, *SORTIE)
    assert counter.inside == 0
    counter.set_inside(9)
    assert counter.inside == 9


def test_lectures_repetees_sans_changement_ignorees():
    counter = PassageCounter(0)
    etapes = [step for step in ENTREE for _ in range(3)]
    assert passe(counter, *etapes) == [Passage.ENTRY]


# ---------------------------------------------------------------------- horaire


def test_plage_horaire():
    schedule = Schedule.parse("07:00", "21:00")
    assert schedule.is_day(datetime(2026, 11, 10, 12, 0))
    assert not schedule.is_day(datetime(2026, 11, 10, 21, 0))
    assert not schedule.is_day(datetime(2026, 11, 10, 6, 59))


def test_plage_horaire_sur_minuit():
    schedule = Schedule.parse("22:00", "02:00")
    assert schedule.is_day(datetime(2026, 11, 10, 23, 0))
    assert schedule.is_day(datetime(2026, 11, 10, 1, 0))
    assert not schedule.is_day(datetime(2026, 11, 10, 12, 0))
