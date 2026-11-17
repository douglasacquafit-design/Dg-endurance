"""Linha de comando: python -m dgendurance <comando>"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from .analise import ResumoSemana, analisar_semana, inicio_semana
from .config import RAIZ, Atleta, Config, carregar_config, carregar_env
from .feedback import Feedback, gerar_feedback
from .prescricao import montar_semana
from .relatorio import ItemRelatorio, gerar_html


def _semanas(ref: date, cfg: Config) -> tuple[date, date]:
    """(semana analisada = última semana completa, semana a prescrever)."""
    atual = inicio_semana(ref)
    return atual - timedelta(days=7), atual + timedelta(days=7 * int(cfg.geral.get("semanas_a_frente", 1)))


def _filtrar(atletas: list[Atleta], nome: str | None) -> list[Atleta]:
    if not nome:
        return atletas
    sel = [a for a in atletas if nome.lower() in a.nome.lower()]
    if not sel:
        sys.exit(f"Nenhum atleta encontrado com '{nome}'.")
    return sel


def _fonte(args: argparse.Namespace, cfg: Config, semana: date):
    if args.demo:
        from .demo import ATLETAS_DEMO, FonteDemo

        cfg.atletas = [a for a, _ in ATLETAS_DEMO]
        return FonteDemo(cfg, semana)
    from .intervals import FonteIntervals, IntervalsClient

    return FonteIntervals(IntervalsClient(os.environ.get("INTERVALS_API_KEY", "")))


def _processar(atleta: Atleta, fonte, cfg: Config, analisada: date, prescrita: date, usar_ia: bool) -> ItemRelatorio:
    erro = None
    try:
        dados = fonte.dados_atleta(atleta.intervals_id, analisada, analisada + timedelta(days=6),
                                   analisada - timedelta(days=42))
    except Exception as e:  # noqa: BLE001 - um atleta com erro não pode travar os outros
        dados, erro = {}, str(e)
    resumo = analisar_semana(atleta, dados, analisada, cfg)
    proxima, fase, motivo = montar_semana(atleta, prescrita, cfg, resumo)
    lista = [{"data": t.data.isoformat(), "treino": t.nome, "tipo": t.tipo, "min": t.duracao_min} for t in proxima]
    if erro:
        fb = Feedback(whatsapp="", notas_treinador=f"Não foi possível buscar os dados: {erro}")
    else:
        fb = gerar_feedback(atleta, resumo, lista, motivo, cfg, usar_ia=usar_ia)
    return ItemRelatorio(atleta, resumo, fb, proxima, fase, motivo, erro)


def cmd_semana(args: argparse.Namespace) -> None:
    cfg = carregar_config()
    ref = date.fromisoformat(args.data) if args.data else date.today()
    analisada, prescrita = _semanas(ref, cfg)
    fonte = _fonte(args, cfg, analisada)
    atletas = _filtrar(cfg.atletas, args.atleta)
    usar_ia = not args.sem_ia
    print(f"Analisando semana {analisada:%d/%m} a {analisada + timedelta(days=6):%d/%m} "
          f"de {len(atletas)} atletas (IA: {'sim' if usar_ia else 'não'})...")

    with ThreadPoolExecutor(max_workers=args.paralelo) as ex:
        futuros = [ex.submit(_processar, a, fonte, cfg, analisada, prescrita, usar_ia) for a in atletas]
        itens = []
        for f in futuros:
            it = f.result()
            itens.append(it)
            print(f"  {'🔴' if it.resumo.status == 'vermelho' else '🟡' if it.resumo.status == 'amarelo' else '🟢'} "
                  f"{it.atleta.nome}: {it.resumo.horas_total}h, {len(it.resumo.alertas)} alerta(s)"
                  + (f" | ERRO: {it.erro}" if it.erro else ""))

    pasta = Path(args.saida) / analisada.isoformat()
    pasta.mkdir(parents=True, exist_ok=True)
    treinador = cfg.geral.get("treinador", {})
    (pasta / "painel.html").write_text(
        gerar_html(itens, analisada, prescrita, treinador.get("nome", ""), treinador.get("equipe", "")),
        encoding="utf-8")
    dados_json = {
        "semana_analisada": analisada.isoformat(), "semana_prescrita": prescrita.isoformat(),
        "demo": bool(args.demo),
        "atletas": [{
            "nome": it.atleta.nome, "intervals_id": it.atleta.intervals_id,
            "resumo": it.resumo.para_dict(), "feedback": asdict(it.feedback),
            "fase_proxima": it.fase_proxima, "motivo": it.motivo,
            "proxima_semana": [t.evento_intervals(it.atleta) for t in it.proxima],
        } for it in itens],
    }
    (pasta / "semana.json").write_text(json.dumps(dados_json, ensure_ascii=False, indent=1, default=str),
                                       encoding="utf-8")
    print(f"\nPronto! Abra o painel: {pasta / 'painel.html'}")
    print(f"Para enviar os treinos da semana {prescrita:%d/%m} aos atletas: "
          f"python -m dgendurance enviar-treinos --pasta {pasta} --confirmar")


def _ler_semana(pasta: str) -> dict:
    arq = Path(pasta) / "semana.json"
    if not arq.exists():
        sys.exit(f"Não encontrei {arq}. Rode 'python -m dgendurance semana' primeiro.")
    return json.loads(arq.read_text(encoding="utf-8"))


def cmd_enviar_treinos(args: argparse.Namespace) -> None:
    dados = _ler_semana(args.pasta)
    if dados.get("demo"):
        sys.exit("Essa pasta é de demonstração: atletas fictícios, nada a enviar.")
    atletas = [a for a in dados["atletas"] if not args.atleta or args.atleta.lower() in a["nome"].lower()]
    total = sum(len(a["proxima_semana"]) for a in atletas)
    print(f"Semana {dados['semana_prescrita']}: {total} treinos para {len(atletas)} atletas.")
    if not args.confirmar:
        for a in atletas:
            print(f"  {a['nome']}: {len(a['proxima_semana'])} treinos ({a['motivo']})")
        print("\nNada foi enviado (simulação). Adicione --confirmar para enviar ao intervals.icu.")
        return
    from .intervals import IntervalsClient

    cli = IntervalsClient(os.environ.get("INTERVALS_API_KEY", ""))
    for a in atletas:
        try:
            cli.gravar_treinos(a["intervals_id"], a["proxima_semana"])
            print(f"  ✓ {a['nome']}: {len(a['proxima_semana'])} treinos no calendário")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {a['nome']}: {e}")


def cmd_comentar(args: argparse.Namespace) -> None:
    dados = _ler_semana(args.pasta)
    if dados.get("demo"):
        sys.exit("Essa pasta é de demonstração: nada a comentar.")
    pares = [(a["nome"], c) for a in dados["atletas"] for c in a["feedback"].get("comentarios_treinos", [])
             if not args.atleta or args.atleta.lower() in a["nome"].lower()]
    if not args.confirmar:
        for nome, c in pares:
            print(f"  {nome} [{c['id']}]: {c['texto']}")
        print(f"\n{len(pares)} comentários. Nada foi publicado. Use --confirmar para publicar no intervals.icu.")
        return
    from .intervals import IntervalsClient

    cli = IntervalsClient(os.environ.get("INTERVALS_API_KEY", ""))
    for nome, c in pares:
        try:
            cli.comentar_atividade(c["id"], c["texto"])
            print(f"  ✓ {nome}: comentário publicado")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {nome}: {e}")


def cmd_testar(args: argparse.Namespace) -> None:
    from .intervals import IntervalsClient

    cfg = carregar_config()
    cli = IntervalsClient(os.environ.get("INTERVALS_API_KEY", ""))
    eu = cli.atleta("0")
    print(f"Conectado ao intervals.icu como: {eu.get('name')} ({eu.get('id')})")
    for a in cfg.atletas:
        try:
            info = cli.atleta(a.intervals_id)
            print(f"  ✓ {a.nome} -> {info.get('name')}")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {a.nome} ({a.intervals_id}): {e}")
    ia = any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"))
    print(f"IA (Anthropic): {'chave configurada' if ia else 'sem chave, os feedbacks usarão o modelo de texto'}")


def main(argv: list[str] | None = None) -> None:
    carregar_env()
    p = argparse.ArgumentParser(prog="dgendurance", description="DG Endurance: análise, feedback e prescrição semanal")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("semana", help="Analisa a última semana, gera feedbacks, a próxima semana e o painel")
    s.add_argument("--data", help="Data de referência AAAA-MM-DD (padrão: hoje)")
    s.add_argument("--demo", action="store_true", help="Usa atletas fictícios (sem conectar contas)")
    s.add_argument("--sem-ia", action="store_true", help="Feedbacks por modelo de texto, sem IA")
    s.add_argument("--atleta", help="Processa só atletas cujo nome contém este texto")
    s.add_argument("--saida", default=str(RAIZ / "saida"), help="Pasta de saída")
    s.add_argument("--paralelo", type=int, default=6, help="Atletas processados em paralelo")
    s.set_defaults(func=cmd_semana)

    e = sub.add_parser("enviar-treinos", help="Envia a semana prescrita ao intervals.icu (-> Garmin/Zwift)")
    e.add_argument("--pasta", required=True, help="Pasta gerada pelo comando 'semana'")
    e.add_argument("--atleta")
    e.add_argument("--confirmar", action="store_true", help="Sem isto, só mostra o que seria enviado")
    e.set_defaults(func=cmd_enviar_treinos)

    c = sub.add_parser("comentar", help="Publica os comentários dos treinos no intervals.icu")
    c.add_argument("--pasta", required=True)
    c.add_argument("--atleta")
    c.add_argument("--confirmar", action="store_true")
    c.set_defaults(func=cmd_comentar)

    t = sub.add_parser("testar-conexao", help="Confere a chave do intervals.icu e o acesso a cada atleta")
    t.set_defaults(func=cmd_testar)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
