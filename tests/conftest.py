from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(object_storage_path=tmp_path / "var")
    return TestClient(create_app(settings))


@pytest.fixture
def sample_pdf_path(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "\n".join(
            [
                "Abstract",
                "This paper proposes a compact reviewer agent kernel for testing.",
                "It extracts paper structure, chunks, references, and warnings.",
                "",
                "1 Introduction",
                "The system starts with a local parsing loop before external retrieval.",
                "Figure 1: Overview of the reviewer workflow.",
                "Table 1: Parser output fields.",
                "",
                "References",
                "[1] Smith, J. Evidence grounded review systems. 2025.",
            ]
        ),
        fontsize=11,
    )
    document.save(pdf_path)
    document.close()
    return pdf_path
