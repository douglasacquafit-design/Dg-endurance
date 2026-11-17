"""Importa o cadastro de atletas de uma planilha (Excel .xlsx ou .csv) para config/atletas.yaml."""
from __future__ import annotations

import csv
import io
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from .config import DIAS, _parse_atleta

# Cabeçalhos aceitos (sem acento, minúsculo) -> campo
COLUNAS = {
    "nome": "nome", "atleta": "nome",
    "intervals_id": "intervals_id", "intervals": "intervals_id", "id intervals": "intervals_id",
    "whatsapp": "whatsapp", "telefone": "whatsapp", "celular": "whatsapp",
    "nivel": "nivel",
    "volume": "volume",
    "ciclo": "ciclo",
    "prova": "prova_nome", "prova alvo": "prova_nome", "prova_nome": "prova_nome",
    "data prova": "prova_data", "data da prova": "prova_data", "prova_data": "prova_data",
    "distancia": "prova_distancia", "prova_distancia": "prova_distancia",
    "folga": "dias_folga", "dias folga": "dias_folga", "dias_folga": "dias_folga", "folgas": "dias_folga",
    "observacoes": "observacoes", "obs": "observacoes", "observacao": "observacoes",
}
NIVEIS = {"iniciante": "iniciante", "intermediario": "intermediario", "avancado": "avancado"}
DISTANCIAS = {"sprint": "sprint", "olimpico": "olimpico", "olimpica": "olimpico", "70.3": "70.3",
              "meio ironman": "70.3", "half": "70.3", "140.6": "140.6", "ironman": "140.6", "full": "140.6"}


def _norm(txt: Any) -> str:
    s = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace("_", " ").split())


def _ler_linhas(arquivo: Path) -> list[dict[str, Any]]:
    if arquivo.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl

        ws = openpyxl.load_workbook(arquivo, data_only=True).active
        linhas = list(ws.iter_rows(values_only=True))
        cab = [str(c or "") for c in linhas[0]]
        return [dict(zip(cab, l)) for l in linhas[1:]]
    bruto = arquivo.read_bytes()
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")  # Excel brasileiro antigo
    sep = ";" if texto.splitlines()[0].count(";") > texto.splitlines()[0].count(",") else ","
    return list(csv.DictReader(io.StringIO(texto), delimiter=sep))


def _data(v: Any) -> str | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"data '{s}' não reconhecida (use dd/mm/aaaa)")


def _folgas(v: Any) -> list[str]:
    if not v:
        return []
    partes = [_norm(p)[:3] for p in str(v).replace("/", ",").replace(";", ",").replace(" e ", ",").split(",")]
    partes = [p for p in partes if p]
    invalidos = [p for p in partes if p not in DIAS]
    if invalidos:
        raise ValueError(f"dia de folga '{', '.join(invalidos)}' inválido (use seg, ter, qua, qui, sex, sab, dom)")
    return partes


def converter_linha(linha: dict[str, Any]) -> dict[str, Any] | None:
    colunas = {_norm(k): v for k, v in COLUNAS.items()}
    d = {colunas[_norm(k)]: v for k, v in linha.items() if _norm(k) in colunas}
    if not str(d.get("nome") or "").strip():
        return None
    a: dict[str, Any] = {"nome": str(d["nome"]).strip(), "intervals_id": str(d.get("intervals_id") or "").strip()}
    tel = "".join(c for c in str(d.get("whatsapp") or "") if c.isdigit())
    if tel and len(tel) <= 11:  # sem DDI: assume Brasil
        tel = "55" + tel
    a["whatsapp"] = tel
    nivel = _norm(d.get("nivel")) or "intermediario"
    if nivel not in NIVEIS:
        raise ValueError(f"nível '{d.get('nivel')}' inválido (iniciante, intermediario, avancado)")
    a["nivel"] = NIVEIS[nivel]
    if d.get("volume") not in (None, ""):
        a["volume"] = float(str(d["volume"]).replace(",", "."))
    if d.get("ciclo") not in (None, ""):
        a["ciclo"] = str(d["ciclo"]).strip()
    if d.get("prova_data"):
        dist = _norm(d.get("prova_distancia")) or "70.3"
        if dist not in DISTANCIAS:
            raise ValueError(f"distância '{d.get('prova_distancia')}' inválida (sprint, olimpico, 70.3, 140.6)")
        a["prova_alvo"] = {"nome": str(d.get("prova_nome") or "Prova alvo").strip(),
                           "data": _data(d["prova_data"]), "distancia": DISTANCIAS[dist]}
    a["dias_folga"] = _folgas(d.get("dias_folga"))
    a["observacoes"] = str(d.get("observacoes") or "").strip()
    _parse_atleta(a)  # valida
    return a


def importar(arquivo: Path) -> tuple[list[dict[str, Any]], list[str]]:
    atletas, erros = [], []
    for i, linha in enumerate(_ler_linhas(arquivo), start=2):
        try:
            a = converter_linha(linha)
            if a:
                atletas.append(a)
                if not a["intervals_id"]:
                    erros.append(f"Linha {i} ({a['nome']}): sem ID do intervals.icu (aviso)")
        except (ValueError, TypeError) as e:
            erros.append(f"Linha {i}: {e}")
    return atletas, erros


def gravar_yaml(atletas: list[dict[str, Any]], destino: Path) -> None:
    cab = ("# Gerado por: python -m dgendurance importar-atletas\n"
           "# Pode editar aqui ou na planilha e importar de novo.\n\n")
    destino.write_text(cab + yaml.safe_dump({"atletas": atletas}, allow_unicode=True, sort_keys=False,
                                            width=120), encoding="utf-8")
