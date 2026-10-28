"""The settings dialogs link to the README (language dependent)."""
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.rollladen_zeiten.const import DOMAIN, docs_url


@pytest.fixture(autouse=True)
def _auto(enable_custom_integrations):
    yield


def test_docs_url_language():
    assert docs_url("de").endswith("#readme")
    assert docs_url("de-AT").endswith("#readme")
    assert docs_url("en").endswith("README.en.md")
    assert docs_url(None).endswith("README.en.md")


async def test_config_form_has_docs_link(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["docs_url"].startswith("https://github.com/Reinhard-M/")
