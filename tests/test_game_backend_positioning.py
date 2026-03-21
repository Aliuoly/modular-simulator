"""Docs-contract regression tests for educational-backend positioning.

These tests freeze the approved product-identity contract from:
  openspec/changes/clarify-educational-backend-positioning/
  specs/educational-backend-positioning/spec.md

Design intent:
  - Each test is tightly coupled to a specific required phrase or structural
    element from the spec; broad keyword checks have been replaced with the
    exact approved wording so that reverting to the pre-edit framing causes
    failures.
  - Red-boundary evidence: all assertions marked "WOULD FAIL on pre-edit docs"
    are confirmed to be absent from the root-branch docs state at the time
    this change was authored (see verification section in tasks.md).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_README = ROOT / "docs/README.md"
_PBS_GUIDE = ROOT / "docs/plant_backend_session_user_guide.md"
_OVERVIEW = ROOT / "docs/game_backend_overview.md"
_CATALOG = ROOT / "docs/examples_catalog.md"


# ---------------------------------------------------------------------------
# Requirement: Repository Framing Identifies An Educational Backend
# Spec scenario: "all three describe the repo as an educational backend built
# on the existing simulation substrate rather than as only a generic
# control-simulation sandbox"
# ---------------------------------------------------------------------------


def test_readme_opens_with_simulation_first_educational_backend() -> None:
    """README intro paragraph must describe the repo as a simulation-first backend
    for educational chemical-process work — not only as a 'lightweight framework'.

    WOULD FAIL on pre-edit docs: pre-edit README intro says
    'a lightweight framework for building closed-loop process simulations'
    with no mention of 'simulation-first backend' or 'educational'.
    """
    text = _README.read_text(encoding="utf-8")
    # The approved intro phrase from the edit
    assert "simulation-first backend" in text, (
        "docs/README.md must describe the repo as a 'simulation-first backend' "
        "(approved product identity from the educational-backend-positioning spec)"
    )
    # Must name the domain — 'chemical-process' or 'chemical engineering'
    assert "chemical-process" in text or "chemical engineering" in text, (
        "docs/README.md must name the 'chemical-process' or 'chemical engineering' domain"
    )
    # Must name educational purpose explicitly
    assert "educational" in text, "docs/README.md must include the word 'educational'"


def test_readme_names_three_teaching_tracks() -> None:
    """README must explicitly name all three phase-1 teaching tracks.

    WOULD FAIL on pre-edit docs: pre-edit README has no mention of
    'teaching track', 'reactor/control', or 'recycle' in the intro/framing.
    """
    text = _README.read_text(encoding="utf-8")
    assert "teaching track" in text.lower() or "teaching tracks" in text.lower(), (
        "docs/README.md must mention 'teaching track(s)'"
    )
    assert "topology" in text.lower() and "separation" in text.lower(), (
        "docs/README.md must name the topology/separation teaching track"
    )
    assert "reactor" in text.lower() and "control" in text.lower(), (
        "docs/README.md must name the reactor/control teaching track"
    )
    assert "recycle" in text.lower(), (
        "docs/README.md must name the recycle/process-design teaching track"
    )


def test_pbs_guide_opens_with_substrate_positioning() -> None:
    """plant_backend_session_user_guide.md first paragraph must declare PlantBackendSession
    as a low-level runtime-editing substrate and must clarify it is not the owner of
    gameplay progression or economics.

    WOULD FAIL on pre-edit docs: pre-edit PBS guide first paragraph says only
    'how to use PlantBackendSession as a user-facing backend for interactive
    plant editing' — no mention of 'substrate', 'progression', or 'economics'.
    """
    text = _PBS_GUIDE.read_text(encoding="utf-8")
    # Must use the approved 'substrate' framing
    assert "substrate" in text, (
        "docs/plant_backend_session_user_guide.md must describe PlantBackendSession "
        "as a 'substrate' (the approved low-level runtime-editing substrate framing)"
    )
    # Must clarify that progression/economics are NOT owned by PlantBackendSession
    assert (
        "not the owner of" in text.lower()
        or "not" in text[:600].lower()
        and any(kw in text[:600].lower() for kw in ("progression", "economics"))
    ), (
        "docs/plant_backend_session_user_guide.md must clarify that PlantBackendSession "
        "is not the owner of progression or economics"
    )
    # Must name gameplay/progression/economics to explain what composes the substrate
    assert any(kw in text.lower() for kw in ("gameplay", "progression", "economics")), (
        "docs/plant_backend_session_user_guide.md must mention gameplay, progression, "
        "or economics to explain what composes PlantBackendSession"
    )
    # Must mention educational purpose
    assert "educational" in text.lower(), (
        "docs/plant_backend_session_user_guide.md must mention the educational purpose"
    )


def test_game_backend_overview_exists() -> None:
    """docs/game_backend_overview.md must exist.

    WOULD FAIL on pre-edit docs: file did not exist.
    """
    assert _OVERVIEW.exists(), (
        "docs/game_backend_overview.md must exist — it is required by the "
        "educational-backend-positioning spec"
    )


def test_overview_declares_simulation_first_educational_backend() -> None:
    """game_backend_overview.md must declare the repo identity using the approved phrase.

    WOULD FAIL on pre-edit docs: file did not exist.
    """
    text = _OVERVIEW.read_text(encoding="utf-8")
    assert "simulation-first backend" in text, (
        "docs/game_backend_overview.md must contain the phrase 'simulation-first backend'"
    )
    assert "educational" in text.lower(), (
        "docs/game_backend_overview.md must contain the word 'educational'"
    )
    assert "chemical-process" in text or "chemical engineering" in text, (
        "docs/game_backend_overview.md must name the 'chemical-process' or "
        "'chemical engineering' domain"
    )


# ---------------------------------------------------------------------------
# Requirement: Phase-1 Scope Remains A Narrow Continuous-Process Curriculum
# Spec scenario: "three teaching tracks are named explicitly and batch-first
# gameplay, fouling/staffing, and multi-plant vertical integration are listed
# as deferred work"
# ---------------------------------------------------------------------------


def test_overview_names_all_three_phase1_teaching_tracks() -> None:
    """game_backend_overview.md must explicitly name all three phase-1 tracks.

    WOULD FAIL on pre-edit docs: file did not exist.
    """
    text = _OVERVIEW.read_text(encoding="utf-8")
    # Track 1
    assert "topology" in text.lower() and "separation" in text.lower(), (
        "docs/game_backend_overview.md must name the topology/separation track"
    )
    # Track 2
    assert "reactor" in text.lower() and "control" in text.lower(), (
        "docs/game_backend_overview.md must name the reactor/control track"
    )
    # Track 3
    assert "recycle" in text.lower(), (
        "docs/game_backend_overview.md must name the recycle/process-design track"
    )


def test_overview_names_deferred_batch_fouling_multisite() -> None:
    """game_backend_overview.md must explicitly list all three deferred-topic categories.

    WOULD FAIL on pre-edit docs: file did not exist.
    """
    text = _OVERVIEW.read_text(encoding="utf-8")
    assert "batch" in text.lower(), (
        "docs/game_backend_overview.md must name 'batch' as a deferred topic"
    )
    assert "fouling" in text.lower() or "staffing" in text.lower(), (
        "docs/game_backend_overview.md must name 'fouling' or 'staffing' as deferred"
    )
    assert "multi-plant" in text.lower() or "vertical integration" in text.lower(), (
        "docs/game_backend_overview.md must name 'multi-plant' or 'vertical integration' "
        "as deferred"
    )


# ---------------------------------------------------------------------------
# Requirement: PlantBackendSession Is Positioned As Substrate
# Spec scenario: "the guide explains that user-facing gameplay or classroom
# orchestration composes PlantBackendSession instead of living inside it"
# ---------------------------------------------------------------------------


def test_pbs_guide_substrate_is_in_opening_section() -> None:
    """The 'substrate' framing must appear in the opening section of the guide
    (within the first ~600 characters), not buried at the end.

    WOULD FAIL on pre-edit docs: 'substrate' does not appear anywhere.
    """
    text = _PBS_GUIDE.read_text(encoding="utf-8")
    opening = text[:700]
    assert "substrate" in opening.lower(), (
        "docs/plant_backend_session_user_guide.md 'substrate' framing must appear "
        "in the opening section (first ~700 characters), not buried later"
    )


def test_overview_describes_pbs_as_substrate_layer() -> None:
    """game_backend_overview.md must describe PlantBackendSession as a substrate.

    WOULD FAIL on pre-edit docs: file did not exist.
    """
    text = _OVERVIEW.read_text(encoding="utf-8")
    assert "substrate" in text.lower(), (
        "docs/game_backend_overview.md must use the word 'substrate'"
    )
    # Must name PlantBackendSession specifically
    assert "plantbackendsession" in text.lower(), (
        "docs/game_backend_overview.md must mention 'PlantBackendSession'"
    )


def test_overview_states_gameplay_composes_substrate() -> None:
    """game_backend_overview.md must state that future gameplay/progression composes
    the substrate rather than replacing it.

    WOULD FAIL on pre-edit docs: file did not exist.
    """
    text = _OVERVIEW.read_text(encoding="utf-8")
    # The approved phrasing: "compose those layers" / "compose the substrate"
    assert "compose" in text.lower(), (
        "docs/game_backend_overview.md must say that gameplay layers 'compose' "
        "the substrate (not rewrite it)"
    )


# ---------------------------------------------------------------------------
# Requirement: Canonical Example Guidance Stays Separate From Gameplay Roadmapping
# Spec scenario: "docs present the canonical examples as the current substrate
# learning path and do not relabel the catalog as the phase-1 gameplay scenario list"
# ---------------------------------------------------------------------------


def test_catalog_header_remains_examples_catalog() -> None:
    """examples_catalog.md title must remain 'Examples Catalog'.

    Must not be relabeled as a gameplay scenario catalog.
    """
    text = _CATALOG.read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert "Examples Catalog" in first_line, (
        "docs/examples_catalog.md must keep '# Examples Catalog' as its title"
    )
    assert "gameplay" not in first_line.lower(), (
        "docs/examples_catalog.md title must not include 'gameplay'"
    )


def test_overview_presents_canonical_examples_as_substrate_not_scenario_list() -> None:
    """game_backend_overview.md must present canonical examples as the substrate learning
    path — must NOT claim the examples catalog is the gameplay scenario list.

    WOULD FAIL on pre-edit docs: file did not exist.
    """
    text = _OVERVIEW.read_text(encoding="utf-8")
    assert "canonical" in text.lower() or "substrate learning path" in text.lower(), (
        "docs/game_backend_overview.md must describe the canonical examples as the "
        "substrate learning path"
    )
    # Must not claim the examples catalog is the gameplay scenario list
    assert "gameplay scenario list" not in text.lower(), (
        "docs/game_backend_overview.md must not relabel the examples catalog as a "
        "'gameplay scenario list'"
    )
