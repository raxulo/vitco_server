"""
Tests for MCC edit form rendering and validation, ensuring fixed_rate_config
and milk_quality_config defaults do not output 'None' and string 'None' parses gracefully.
"""
from uuid import uuid4
import pytest
from jinja2 import Environment, FileSystemLoader

from app.modules.mcc.presentation.requests import UpdateMccRequest, CreateMccRequest
from app.modules.mcc.domain.enums import MccType
from app.web.mcc.assembler import MccAssembler


def test_mcc_create_edit_template_renders_without_none_values():
    env = Environment(loader=FileSystemLoader("app/web/templates"))
    env.globals["url_for"] = lambda name, **kwargs: f"/static/{kwargs.get('path', '')}"
    env.globals["request"] = {"url": "http://localhost/mcc/edit"}
    template = env.get_template("pages/mcc/create_edit.html")

    # Simulate an MCC of NORMAL type where fixed_rate_config is None
    mcc_mock = {
        "id": uuid4(),
        "code": "1001",
        "name": "Test MCC",
        "mcc_type": MccType.NORMAL,
        "is_active": True,
        "visible_member": True,
        "route_code": None,
        "sample_start": None,
        "sample_end": None,
    }
    user_mock = {
        "email": "testmcc@gmail.com",
        "mobile": "9876543210",
    }
    
    html = template.render(
        mcc=mcc_mock,
        user=user_mock,
        bank_account=None,
        address=None,
        setting=None,
        milk_quality_config=None,
        fixed_rate_config=None,
        device_item_versions=[],
        routes=[],
    )

    # Ensure none of the inputs have value="None"
    assert 'value="None"' not in html
    # Check that default fallback 6.6 was rendered for min_fat
    assert 'name="min_fat"' in html
    assert 'value="6.6"' in html


def test_update_mcc_request_handles_none_and_empty_strings():
    # If a client submits 'None' or empty string for min_fat/max_fat
    data = {
        "code": "1001",
        "name": "Test MCC",
        "email": "test@mcc.com",
        "mobile": "9876543210",
        "min_fat": "None",
        "max_fat": "null",
        "min_snf": "",
        "max_snf": "undefined",
        "fixed_rate": "None",
    }
    req = UpdateMccRequest.model_validate(data)
    assert req.min_fat is None
    assert req.max_fat is None
    assert req.min_snf is None
    assert req.max_snf is None
    assert req.fixed_rate is None


def test_mcc_assembler_update_with_none_fixed_rate_values():
    data = {
        "code": "1001",
        "name": "Test MCC",
        "email": "test@mcc.com",
        "mobile": "9876543210",
        "mcc_type": MccType.FIXED_RATE,
        "min_fat": None,
        "max_fat": None,
        "min_snf": None,
        "max_snf": None,
    }
    req = UpdateMccRequest.model_validate(data)
    cmd = MccAssembler.update(req, id=uuid4(), updated_by=uuid4())
    
    assert cmd.fixed_rate_config is not None
    assert cmd.fixed_rate_config.min_fat == 0.0
    assert cmd.fixed_rate_config.max_fat == 0.0
