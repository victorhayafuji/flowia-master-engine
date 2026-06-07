"""Organizações de referência para seed do Data Lake (MVP salão)."""

SALON_ORG_ID = "22222222-2222-2222-2222-222222222222"

VERTICAL_ORGS = {
    "salon": {
        "id": SALON_ORG_ID,
        "name": "Salão Beauty Express",
        "slug": "salao-beauty-express",
        "vertical": "salon",
        "search_query": "quanto custa corte feminino",
        "ensure_org": True,
    },
}

_DEPRECATED_ORGS = ("dental", "medical", "flowia")
