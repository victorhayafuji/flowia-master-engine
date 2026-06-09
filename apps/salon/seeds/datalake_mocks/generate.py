"""Generate text mock documents for local Data Lake seed."""

from __future__ import annotations

import tempfile
from pathlib import Path

_SALON_DOCS: dict[str, str] = {
    "tabela_precos_salao.txt": (
        "SALAO BEAUTY EXPRESS - TABELA DE PRECOS 2026\n\n"
        "* Corte Masculino: R$ 80 (30 min)\n"
        "* Corte Feminino: R$ 120 (60 min)\n"
        "* Coloracao: R$ 250 (120 min)\n"
        "* Manicure: R$ 45 (45 min)\n"
        "* Barba: R$ 50 (30 min)\n\n"
        "Horario: segunda a sabado, 09h as 18h.\n"
        "Cancelamento: avisar com 24h de antecedencia."
    ),
    "politicas_atendimento.txt": (
        "POLITICAS DE ATENDIMENTO - BEAUTY EXPRESS\n\n"
        "Atrasos acima de 15 minutos podem resultar em reagendamento.\n"
        "Pagamento: PIX, cartao debito/credito e dinheiro.\n"
        "Mechas e coloracao exigem avaliacao previa quando indicado pelo salao."
    ),
}


def generate_documents(vertical: str) -> list[Path]:
    """Write synthetic docs to a temp dir and return paths (salon MVP only)."""
    if vertical != "salon":
        raise ValueError(f"Vertical nao suportada para mocks: {vertical}")

    out_dir = Path(tempfile.mkdtemp(prefix="flowia_datalake_mocks_"))
    paths: list[Path] = []
    for name, body in _SALON_DOCS.items():
        path = out_dir / name
        path.write_text(body, encoding="utf-8")
        paths.append(path)
    return paths
