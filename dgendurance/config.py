"""Leitura dos arquivos de configuração (config/, biblioteca/)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PASTA_TREINADORES = RAIZ / "treinadores"
DIAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


def _ler_yaml(caminho: Path) -> dict[str, Any]:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def ler_env(caminho: Path) -> dict[str, str]:
    """Lê um arquivo .env simples (CHAVE=valor)."""
    valores: dict[str, str] = {}
    if not caminho.exists():
        return valores
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        if valor:
            valores[chave.strip()] = valor
    return valores


def carregar_env(caminho: Path | None = None) -> None:
    """Carrega o .env principal (do dono do sistema) no ambiente, sem sobrescrever."""
    for chave, valor in ler_env(caminho or RAIZ / ".env").items():
        os.environ.setdefault(chave, valor)


def _mesclar(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = _mesclar(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def listar_treinadores() -> list[str]:
    if not PASTA_TREINADORES.exists():
        return []
    return sorted(p.name for p in PASTA_TREINADORES.iterdir()
                  if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "config.yaml").exists())


@dataclass
class ProvaAlvo:
    nome: str
    data: date
    distancia: str = "70.3"


@dataclass
class Atleta:
    nome: str
    intervals_id: str
    whatsapp: str = ""
    nivel: str = "intermediario"
    volume: float = 1.0
    prova_alvo: ProvaAlvo | None = None
    dias_folga: list[str] = field(default_factory=list)
    observacoes: str = ""
    ciclo: str | None = None  # "3:1", "2:1", "livre" (None = padrão do config.yaml)

    @property
    def primeiro_nome(self) -> str:
        return self.nome.split()[0]

    @property
    def slug(self) -> str:
        import unicodedata

        s = unicodedata.normalize("NFKD", self.nome).encode("ascii", "ignore").decode()
        return "-".join(s.lower().split())


@dataclass
class Config:
    geral: dict[str, Any]
    atletas: list[Atleta]
    estilo_feedback: str
    treinos: dict[str, dict[str, Any]]
    semanas: dict[str, Any]
    treinador: str | None = None          # None = dono do sistema (pasta config/)
    pasta: Path = RAIZ / "config"         # onde ficam atletas.yaml, estilo etc.
    segredos: dict[str, str] = field(default_factory=dict)

    def segredo(self, nome: str) -> str:
        """Chave do treinador. Só a chave da IA pode vir do dono do sistema (ele paga no piloto);
        a do intervals.icu é sempre do próprio treinador: nunca se mistura dados de equipes."""
        if nome in self.segredos:
            return self.segredos[nome]
        if self.treinador is None or nome in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            return os.environ.get(nome, "")
        return ""

    @property
    def alertas(self) -> dict[str, Any]:
        return self.geral.get("alertas", {})

    @property
    def ia(self) -> dict[str, Any]:
        return self.geral.get("ia", {})


def _parse_atleta(d: dict[str, Any]) -> Atleta:
    prova = None
    if d.get("prova_alvo") and d["prova_alvo"].get("data"):
        p = d["prova_alvo"]
        data_prova = p["data"] if isinstance(p["data"], date) else date.fromisoformat(str(p["data"]))
        prova = ProvaAlvo(nome=p.get("nome", "Prova alvo"), data=data_prova,
                          distancia=str(p.get("distancia", "70.3")))
    folga = [str(x).lower()[:3] for x in d.get("dias_folga") or []]
    invalidos = [x for x in folga if x not in DIAS]
    if invalidos:
        raise ValueError(f"Atleta {d.get('nome')}: dia de folga inválido {invalidos}. Use {DIAS}")
    return Atleta(
        nome=d["nome"],
        intervals_id=str(d.get("intervals_id", "")),
        whatsapp="".join(c for c in str(d.get("whatsapp", "")) if c.isdigit()),
        nivel=d.get("nivel", "intermediario"),
        volume=float(d.get("volume", 1.0)),
        prova_alvo=prova,
        dias_folga=folga,
        observacoes=d.get("observacoes", ""),
        ciclo=_parse_ciclo(d.get("ciclo"), d.get("nome")),
    )


def _parse_ciclo(valor: Any, nome: Any = "") -> str | None:
    if valor in (None, ""):
        return None
    v = str(valor).strip().lower()
    if v in ("livre", "nenhum", "0"):
        return "livre"
    if not re.fullmatch(r"\d+:1", v):
        raise ValueError(f"Atleta {nome}: ciclo '{valor}' inválido. Use '3:1', '2:1' ou 'livre'.")
    return v


def semanas_do_ciclo(ciclo: str | None) -> int:
    """'3:1' -> 4 (a cada 4 semanas, 1 é de recuperação). 'livre' -> 0."""
    if not ciclo or ciclo == "livre":
        return 0
    return int(ciclo.split(":")[0]) + 1


def carregar_config(raiz: Path = RAIZ, arquivo_atletas: Path | None = None,
                    treinador: str | None = None) -> Config:
    """Carrega a configuração do dono (treinador=None) ou de um treinador do piloto.

    Treinador: treinadores/<slug>/ com config.yaml (só o que muda), atletas.yaml,
    estilo_feedback.md, segredos.env e, opcionalmente, biblioteca/ própria.
    O que não existir na pasta dele vem da configuração principal.
    """
    geral = _ler_yaml(raiz / "config" / "config.yaml")
    pasta = raiz / "config"
    segredos: dict[str, str] = {}
    bib = raiz / "biblioteca"
    if treinador:
        pasta = raiz / "treinadores" / treinador
        if not (pasta / "config.yaml").exists():
            disponiveis = ", ".join(listar_treinadores()) or "nenhum"
            raise ValueError(f"Treinador '{treinador}' não encontrado. Cadastrados: {disponiveis}. "
                             f"Crie com: python -m dgendurance novo-treinador \"Nome\"")
        geral = _mesclar(geral, _ler_yaml(pasta / "config.yaml"))
        segredos = ler_env(pasta / "segredos.env")
        if (pasta / "biblioteca" / "treinos.yaml").exists():
            bib = pasta / "biblioteca"
    arquivo_atletas = arquivo_atletas or pasta / "atletas.yaml"
    atletas = []
    if arquivo_atletas.exists():  # sem cadastro ainda: só o modo --demo funciona
        atletas = [_parse_atleta(a) for a in _ler_yaml(arquivo_atletas).get("atletas", [])]
    estilo_path = pasta / "estilo_feedback.md"
    if not estilo_path.exists():
        estilo_path = raiz / "config" / "estilo_feedback.md"
    estilo = estilo_path.read_text(encoding="utf-8") if estilo_path.exists() else ""
    treinos = _ler_yaml(bib / "treinos.yaml").get("treinos", {})
    semanas_path = bib / "semanas.yaml" if (bib / "semanas.yaml").exists() else raiz / "biblioteca" / "semanas.yaml"
    semanas = _ler_yaml(semanas_path)
    cfg = Config(geral=geral, atletas=atletas, estilo_feedback=estilo, treinos=treinos, semanas=semanas,
                 treinador=treinador, pasta=pasta, segredos=segredos)
    _validar_biblioteca(cfg)
    return cfg


def _validar_biblioteca(cfg: Config) -> None:
    for fase, dias in cfg.semanas.get("semanas", {}).items():
        for dia, lista in (dias or {}).items():
            if dia not in DIAS:
                raise ValueError(f"semanas.yaml: dia inválido '{dia}' na fase '{fase}'")
            for t in lista or []:
                if t not in cfg.treinos:
                    raise ValueError(f"semanas.yaml: treino '{t}' (fase {fase}, {dia}) não existe em treinos.yaml")
