"""Montagem da semana de treinos a partir dos modelos (biblioteca/) e envio ao intervals.icu."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .analise import VERMELHO, AMARELO, ResumoSemana, fase_treino
from .config import DIAS, Atleta, Config, semanas_do_ciclo

_PASSO = re.compile(r"^(\d+(?:\.\d+)?)(h|mtr|km|m|s)((?:\d+s)?)(?=\s|$)")
_REPETICAO = re.compile(r"^\d+x$")


@dataclass
class TreinoPrescrito:
    data: date
    chave: str
    esporte: str
    nome: str
    tipo: str
    descricao: str
    duracao_min: int

    def evento_intervals(self, atleta: Atleta) -> dict[str, Any]:
        return {
            "category": "WORKOUT",
            "start_date_local": f"{self.data.isoformat()}T00:00:00",
            "type": self.esporte,
            "name": self.nome,
            "description": self.descricao,
            # external_id fixo: rodar de novo atualiza em vez de duplicar
            "external_id": f"dg-{atleta.slug}-{self.data.isoformat()}-{self.chave}",
        }


def escalar_passo(passo: str, fator: float) -> str:
    """Multiplica a duração/distância de um passo. Ex.: '60m 65-75%' x1.5 -> '90m 65-75%'."""
    m = _PASSO.match(passo)
    if not m or fator == 1:
        return passo
    valor, unidade, extra_s = float(m.group(1)), m.group(2), m.group(3)
    resto = passo[m.end():]
    if unidade == "mtr":
        novo = max(50, int(round(valor * fator / 50) * 50))
        return f"{novo}mtr{resto}"
    if unidade == "km":
        return f"{round(valor * fator, 1):g}km{resto}"
    segundos = valor * {"h": 3600, "m": 60, "s": 1}[unidade] + (int(extra_s[:-1]) if extra_s else 0)
    segundos *= fator
    if segundos >= 600:  # passos longos: arredonda para 5 min
        return f"{int(max(5, round(segundos / 300) * 5))}m{resto}"
    minutos, seg = divmod(int(round(segundos / 15) * 15), 60)
    if minutos and seg:
        return f"{minutos}m{seg}s{resto}"
    return f"{minutos}m{resto}" if minutos else f"{max(seg, 15)}s{resto}"


def _duracao_passo_min(passo: str) -> float:
    m = _PASSO.match(passo.lstrip("- ").strip())
    if not m:
        return 0.0
    valor, unidade, extra_s = float(m.group(1)), m.group(2), m.group(3)
    if unidade == "mtr":
        return valor / 1000 * 20  # ~2:00/100m como estimativa
    if unidade == "km":
        return valor * 6
    seg = valor * {"h": 3600, "m": 60, "s": 1}[unidade] + (int(extra_s[:-1]) if extra_s else 0)
    return seg / 60


def renderizar_treino(treino: dict[str, Any], fator: float = 1.0) -> tuple[str, int]:
    """Gera o texto de treino estruturado do intervals.icu e a duração estimada (min)."""
    linhas: list[str] = []
    if treino.get("objetivo"):
        linhas += [treino["objetivo"], ""]
    total = 0.0
    for bloco in treino.get("blocos", []):
        escala = fator if bloco.get("escala") else 1.0
        reps = int(bloco.get("repetir", 1))
        passos = list(bloco.get("passos", []))
        if reps > 1:
            reps = max(1, math.floor(reps * escala + 0.5))
            escala = 1.0
        titulo = bloco.get("titulo", "")
        linhas.append(f"{titulo} {reps}x".strip() if reps > 1 else titulo)
        sub_reps = 1
        for p in passos:
            p = str(p).strip()
            if _REPETICAO.match(p):  # repetição interna (ex.: "3x" seguido de "- 1m 100%")
                linhas.append(p)
                sub_reps = int(p[:-1])
            elif p.startswith("- "):
                linhas.append(p)
                total += _duracao_passo_min(p) * sub_reps * reps
            elif _PASSO.match(p):
                novo = escalar_passo(p, escala)
                linhas.append(f"- {novo}")
                total += _duracao_passo_min(novo) * reps
                sub_reps = 1
            else:
                linhas.append(p)  # observação em texto livre
        linhas.append("")
    return "\n".join(linhas).strip() + "\n", round(total)


def _distribuir_folgas(semana: dict[str, list[str]], folgas: list[str]) -> dict[str, list[str]]:
    """Move treinos de dias de folga para o próximo dia disponível com menos sessões."""
    resultado = {d: list(semana.get(d) or []) for d in DIAS}
    livres = [d for d in DIAS if d not in folgas]
    if not livres:
        return resultado
    for dia in folgas:
        for treino in resultado[dia]:
            idx = DIAS.index(dia)
            candidatos = [DIAS[(idx + k) % 7] for k in range(1, 7) if DIAS[(idx + k) % 7] in livres]
            destino = min(candidatos, key=lambda d: (len(resultado[d]), candidatos.index(d)))
            resultado[destino].append(treino)
        resultado[dia] = []
    return resultado


def escolher_fase(atleta: Atleta, semana: date, resumo: ResumoSemana | None, cfg: Config) -> tuple[str, float, str]:
    """Decide a semana do atleta. Retorna (fase, fator de volume, motivo).

    - dor/lesão ou fadiga em VERMELHO  -> semana de recuperação
    - faltou muito / sumiu (VERMELHO)  -> mesma fase, volume -20% para retomar (tem prioridade
                                          sobre a recuperação programada)
    - fadiga/bem-estar em AMARELO      -> mesma fase, volume -15%
    - ciclo do atleta (ex. 3:1), contado até a prova -> recuperação programada
    """
    fase, semanas = fase_treino(atleta, semana)
    alertas = resumo.alertas if resumo else []
    vermelhos = {a.categoria for a in alertas if a.nivel == VERMELHO}
    amarelos = {a.categoria for a in alertas if a.nivel == AMARELO}

    if fase != "polimento" and vermelhos & {"dor", "fadiga"}:
        motivo = "relato de dor/lesão" if "dor" in vermelhos else "fadiga muito alta"
        return "recuperacao", 1.0, f"semana de recuperação ({motivo})"
    if "cumprimento" in vermelhos:  # já descansou: retomar, não recuperar
        return fase, 0.8, f"fase de {fase}, volume -20% para retomar o ritmo"
    n = semanas_do_ciclo(atleta.ciclo or cfg.geral.get("ciclo_padrao", "3:1"))
    ciclo = semanas if semanas is not None else semana.isocalendar().week
    if n and fase in ("base", "construcao") and ciclo % n == 0:
        return "recuperacao", 1.0, f"semana de recuperação programada (a cada {n})"
    sufixo = f" ({semanas} semanas para a prova)" if semanas is not None else ""
    if amarelos & {"fadiga", "bem_estar"}:
        return fase, 0.85, f"fase de {fase}, volume -15% (sinais de fadiga)"
    return fase, 1.0, f"fase de {fase}{sufixo}"


def montar_semana(atleta: Atleta, semana: date, cfg: Config,
                  resumo: ResumoSemana | None = None) -> tuple[list[TreinoPrescrito], str, str]:
    fase, ajuste, motivo = escolher_fase(atleta, semana, resumo, cfg)
    modelo = cfg.semanas["semanas"][fase]
    dist = atleta.prova_alvo.distancia if atleta.prova_alvo else "70.3"
    fator = (atleta.volume
             * float(cfg.semanas.get("fator_distancia", {}).get(dist, 1.0))
             * float(cfg.semanas.get("fator_nivel", {}).get(atleta.nivel, 1.0))
             * ajuste)
    if fase in ("recuperacao", "polimento"):
        fator = min(fator, 1.0)
    dias = _distribuir_folgas(modelo, atleta.dias_folga)
    treinos: list[TreinoPrescrito] = []
    for i, dia in enumerate(DIAS):
        for chave in dias[dia]:
            t = cfg.treinos[chave]
            descricao, duracao = renderizar_treino(t, fator)
            treinos.append(TreinoPrescrito(
                data=semana + timedelta(days=i), chave=chave, esporte=t["esporte"],
                nome=t["nome"], tipo=t.get("tipo", ""), descricao=descricao, duracao_min=duracao,
            ))
    return treinos, fase, motivo
