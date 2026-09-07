"""Legal document routes.

Serves the Privacy Policy, Terms and Conditions, and Accessibility
Statement as JSON responses. These routes do NOT require authentication
(spec Part 35: legal pages must be accessible without login).

All documents accurately describe DASH's actual data practices.
"""

from __future__ import annotations

from fastapi import APIRouter

from dash_backend.legal.privacy import (
    PRIVACY_POLICY,
    PRIVACY_POLICY_EFFECTIVE,
    PRIVACY_POLICY_VERSION,
)
from dash_backend.legal.terms import (
    TERMS_AND_CONDITIONS,
    TERMS_EFFECTIVE,
    TERMS_VERSION,
)
from dash_backend.legal.accessibility import (
    ACCESSIBILITY_EFFECTIVE,
    ACCESSIBILITY_STATEMENT,
    ACCESSIBILITY_VERSION,
)

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/privacy")
async def get_privacy_policy() -> dict:
    """Return the Privacy Policy.

    No authentication required. This endpoint exists so that legal
    documents are always accessible (spec Part 35).
    """
    return {
        "document": "privacy_policy",
        "version": PRIVACY_POLICY_VERSION,
        "effective_date": PRIVACY_POLICY_EFFECTIVE,
        "content": PRIVACY_POLICY,
    }


@router.get("/terms")
async def get_terms() -> dict:
    """Return the Terms and Conditions.

    No authentication required.
    """
    return {
        "document": "terms_and_conditions",
        "version": TERMS_VERSION,
        "effective_date": TERMS_EFFECTIVE,
        "content": TERMS_AND_CONDITIONS,
    }


@router.get("/accessibility")
async def get_accessibility_statement() -> dict:
    """Return the Accessibility Statement.

    No authentication required.
    """
    return {
        "document": "accessibility_statement",
        "version": ACCESSIBILITY_VERSION,
        "effective_date": ACCESSIBILITY_EFFECTIVE,
        "content": ACCESSIBILITY_STATEMENT,
    }


@router.get("/")
async def list_legal_documents() -> dict:
    """List available legal documents with their versions and dates."""
    return {
        "documents": [
            {
                "id": "privacy",
                "name": "Privacy Policy",
                "version": PRIVACY_POLICY_VERSION,
                "effective_date": PRIVACY_POLICY_EFFECTIVE,
                "endpoint": "/api/v1/legal/privacy",
            },
            {
                "id": "terms",
                "name": "Terms and Conditions",
                "version": TERMS_VERSION,
                "effective_date": TERMS_EFFECTIVE,
                "endpoint": "/api/v1/legal/terms",
            },
            {
                "id": "accessibility",
                "name": "Accessibility Statement",
                "version": ACCESSIBILITY_VERSION,
                "effective_date": ACCESSIBILITY_EFFECTIVE,
                "endpoint": "/api/v1/legal/accessibility",
            },
        ]
    }
