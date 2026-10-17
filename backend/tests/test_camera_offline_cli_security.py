"""Offline CLI refuses demo, production, forged actors and non-admin tokens."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from run_phase3i_offline_reference import authenticated_offline_principal  # noqa: E402

TOKENS={
    "ci-offline-admin":"SECRET_ci_admin_0123456789012345678901",
    "ci-offline-reviewer":"SECRET_ci_reviewer_01234567890123456",
}
PERMISSIONS={
    "ci-offline-admin":{"role":"network_admin","centres":[]},
    "ci-offline-reviewer":{"role":"centre_reviewer","centres":["DEMO-KA-104"]},
}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow_artifact")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","token")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON",json.dumps(TOKENS))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON",json.dumps(PERMISSIONS))
    monkeypatch.setenv("KAUSHALWATCH_PHASE3I_OFFLINE_TOKEN",TOKENS["ci-offline-admin"])


def test_only_authorized_network_admin_token_creates_principal(env):
    officer=authenticated_offline_principal()
    assert officer.actor=="ci-offline-admin"
    assert officer.role=="network_admin"


@pytest.mark.parametrize("token",[
    "", "unknown-secret-01234567890123456789012345678",
    TOKENS["ci-offline-reviewer"],
])
def test_missing_unknown_or_wrong_role_token_fails(env,monkeypatch,token):
    monkeypatch.setenv("KAUSHALWATCH_PHASE3I_OFFLINE_TOKEN",token)
    with pytest.raises(RuntimeError):
        authenticated_offline_principal()


@pytest.mark.parametrize("environment",["production","pilot","development"])
def test_nonstaging_modes_cannot_execute(env,monkeypatch,environment):
    monkeypatch.setenv("KAUSHALWATCH_ENV",environment)
    with pytest.raises(RuntimeError,match="staging"):
        authenticated_offline_principal()


def test_oidc_is_not_impersonated_by_using_a_display_name(env,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","oidc")
    with pytest.raises(RuntimeError,match="staging token"):
        authenticated_offline_principal()


def test_actor_label_is_never_accepted_as_token(env,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_PHASE3I_OFFLINE_TOKEN","ci-offline-admin")
    with pytest.raises(RuntimeError,match="not authorized"):
        authenticated_offline_principal()
