"""Rascunhos de feedback semanal: IA (Claude) ou modelo de texto (sem IA)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .analise import NOME_ESPORTE, VERMELHO, ResumoSemana
from .config import Atleta, Config


@dataclass
class Feedback:
    whatsapp: str
    comentarios_treinos: list[dict[str, str]] = field(default_factory=list)  # [{id, texto}]
    notas_treinador: str = ""
    ajustes_sugeridos: list[str] = field(default_factory=list)
    gerado_por: str = "modelo"


ESQUEMA = {
    "type": "object",
    "properties": {
        "whatsapp": {"type": "string",
                     "description": "Mensagem semanal para o atleta, pronta para enviar no WhatsApp."},
        "comentarios_treinos": {
            "type": "array",
            "description": "Comentários curtos (1-2 frases) para os treinos que merecem comentário.",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "texto": {"type": "string"}},
                "required": ["id", "texto"],
                "additionalProperties": False,
            },
        },
        "notas_treinador": {"type": "string",
                            "description": "Análise técnica para o treinador (não vai para o atleta)."},
        "ajustes_sugeridos": {"type": "array", "items": {"type": "string"},
                              "description": "Ajustes sugeridos para a próxima semana de treinos."},
    },
    "required": ["whatsapp", "comentarios_treinos", "notas_treinador", "ajustes_sugeridos"],
    "additionalProperties": False,
}

SISTEMA = """Você é o assistente de um treinador de triatlo brasileiro. Sua função é preparar \
RASCUNHOS que o treinador revisa antes de enviar. Escreva sempre em português do Brasil, na voz \
do próprio treinador (primeira pessoa), seguindo rigorosamente o guia de estilo abaixo.

Você recebe os dados da semana de um atleta (volume, carga, cumprimento do plano, forma, \
bem-estar, comentários do atleta e alertas automáticos) e produz:
1. "whatsapp": a mensagem semanal para o atleta.
2. "comentarios_treinos": comentários curtos para os 1 a 3 treinos mais relevantes da semana \
(use o "id" do treino), para o treinador colar no TrainingPeaks / intervals.icu.
3. "notas_treinador": 3 a 6 linhas objetivas para o treinador: o que observar, riscos, \
pontos que exigem a decisão dele. Pode usar termos técnicos (CTL, TSB, IF).
4. "ajustes_sugeridos": ajustes concretos para a próxima semana (ou lista vazia).

Regras de segurança: nunca dê diagnóstico médico. Se houver relato de dor, lesão ou doença, \
a mensagem deve acolher, pedir mais detalhes e sugerir cautela, e as notas devem destacar isso. \
Não invente dados que não estão no resumo.

=== GUIA DE ESTILO DO TREINADOR ===
{estilo}
"""


def _contexto(atleta: Atleta, r: ResumoSemana, proxima: list[dict[str, Any]], motivo: str) -> str:
    dados = r.para_dict()
    dados["perfil"] = {
        "nome": atleta.nome, "nivel": atleta.nivel,
        "prova_alvo": (f"{atleta.prova_alvo.nome} ({atleta.prova_alvo.distancia}) em "
                       f"{atleta.prova_alvo.data.strftime('%d/%m/%Y')}") if atleta.prova_alvo else None,
        "observacoes": atleta.observacoes,
    }
    dados["proxima_semana"] = {"motivo": motivo, "treinos": proxima}
    return ("Dados da semana do atleta (JSON):\n\n"
            + json.dumps(dados, ensure_ascii=False, indent=1, default=str))


def gerar_feedback_ia(atleta: Atleta, r: ResumoSemana, proxima: list[dict[str, Any]],
                      motivo: str, cfg: Config, cliente: Any = None) -> Feedback:
    import anthropic

    if cliente is None:
        chave = cfg.segredo("ANTHROPIC_API_KEY")
        cliente = anthropic.Anthropic(api_key=chave) if chave else anthropic.Anthropic()
    resposta = cliente.beta.messages.create(
        model=cfg.ia.get("modelo", "claude-opus-5-5"),
        max_tokens=16000,
        # Prompt de sistema igual para todos os atletas -> cacheado (mais barato)
        system=[{"type": "text", "text": SISTEMA.format(estilo=cfg.estilo_feedback),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _contexto(atleta, r, proxima, motivo)}],
        output_config={"effort": cfg.ia.get("esforco", "medium"),
                       "format": {"type": "json_schema", "schema": ESQUEMA}},
        # Se o modelo recusar por engano, tenta automaticamente outro modelo
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("A IA recusou gerar este feedback.")
    if resposta.stop_reason == "max_tokens":
        raise RuntimeError("Resposta da IA cortada (max_tokens).")
    texto = next(b.text for b in resposta.content if b.type == "text")
    d = json.loads(texto)
    return Feedback(whatsapp=d["whatsapp"], comentarios_treinos=d["comentarios_treinos"],
                    notas_treinador=d["notas_treinador"], ajustes_sugeridos=d["ajustes_sugeridos"],
                    gerado_por="ia")


def gerar_feedback_modelo(atleta: Atleta, r: ResumoSemana, motivo: str) -> Feedback:
    """Feedback sem IA, montado por regras. Útil sem chave da Anthropic ou para testes."""
    nome = atleta.primeiro_nome
    linhas = []
    if r.status == VERMELHO and any("dor" in a.texto.lower() or "lesão" in a.texto.lower() for a in r.alertas):
        linhas.append(f"Fala, {nome}! Vi seu comentário sobre dor. Me conta melhor como está? "
                      "Por segurança, vamos pegar leve nesse esporte até conversarmos.")
    elif r.horas_total == 0:
        linhas.append(f"E aí, {nome}, tudo bem? Não vi treinos registrados essa semana. "
                      "Aconteceu alguma coisa? Me conta que a gente ajusta.")
    else:
        destaque = max(r.por_esporte.items(), key=lambda kv: kv[1]["horas"], default=None)
        txt = f"Fala, {nome}! Semana com {r.horas_total}h de treino"
        if r.cumprimento is not None:
            txt += f" e {r.cumprimento:.0%} do planejado cumprido"
        linhas.append(txt + (" 👏" if (r.cumprimento or 0) >= 0.9 else "."))
        if destaque:
            esp, s = destaque
            linhas.append(f"{NOME_ESPORTE[esp]} foi o destaque: {s['sessoes']:.0f} sessões, {s['km']} km.")
        if r.treinos_perdidos:
            linhas.append(f"Ficaram {len(r.treinos_perdidos)} treinos pelo caminho. "
                          "Me conta o que pegou que eu ajusto.")
        if r.tsb is not None and r.tsb < -20:
            linhas.append("Você está carregando bastante fadiga, então capriche no sono e na alimentação.")
    linhas.append(f"Próxima semana: {motivo}. Bora! 💪")
    notas = "; ".join(a.texto for a in r.alertas) or "Sem alertas."
    return Feedback(whatsapp="\n".join(linhas), notas_treinador=notas, gerado_por="modelo")


def gerar_feedback(atleta: Atleta, r: ResumoSemana, proxima: list[dict[str, Any]], motivo: str,
                   cfg: Config, usar_ia: bool = True) -> Feedback:
    tem_credencial = any(cfg.segredo(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"))
    if usar_ia and cfg.ia.get("ativa", True) and tem_credencial:
        try:
            return gerar_feedback_ia(atleta, r, proxima, motivo, cfg)
        except Exception as e:  # noqa: BLE001 - nunca travar o relatório por causa da IA
            fb = gerar_feedback_modelo(atleta, r, motivo)
            fb.notas_treinador = f"[IA indisponível: {e}] " + fb.notas_treinador
            return fb
    return gerar_feedback_modelo(atleta, r, motivo)
