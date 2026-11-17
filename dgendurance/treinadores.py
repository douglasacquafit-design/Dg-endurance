"""Cadastro de treinadores do piloto (uma pasta por treinador em treinadores/)."""
from __future__ import annotations

import shutil
import unicodedata

from pathlib import Path

from .config import PASTA_TREINADORES, RAIZ

MODELO = PASTA_TREINADORES / "_modelo"


def gerar_slug(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(c if c.isalnum() else " " for c in s).split())


def criar_treinador(nome: str, equipe: str | None = None, slug: str | None = None) -> Path:
    slug = gerar_slug(slug or nome)
    if not slug or slug.startswith("_"):
        raise ValueError(f"Nome inválido para pasta: '{nome}'")
    pasta = PASTA_TREINADORES / slug
    if pasta.exists():
        raise ValueError(f"Já existe um treinador '{slug}' em {pasta}")
    pasta.mkdir(parents=True)
    equipe = equipe or nome
    config = (MODELO / "config.yaml").read_text(encoding="utf-8")
    config = config.replace("{{NOME}}", nome.replace('"', "'")).replace("{{EQUIPE}}", equipe.replace('"', "'"))
    (pasta / "config.yaml").write_text(config, encoding="utf-8")
    shutil.copy(MODELO / "estilo_feedback.md", pasta / "estilo_feedback.md")
    shutil.copy(MODELO / "segredos.env.exemplo", pasta / "segredos.env")
    shutil.copy(RAIZ / "config" / "atletas_modelo.xlsx", pasta / "atletas_modelo.xlsx")
    return pasta
