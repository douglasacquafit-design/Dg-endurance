"""Painel semanal do treinador (HTML único, funciona offline no celular ou computador)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from html import escape
from typing import Any

from .analise import NOME_ESPORTE, VERMELHO, AMARELO, VERDE, ResumoSemana
from .config import Atleta
from .feedback import Feedback
from .prescricao import TreinoPrescrito
from .whatsapp import link_whatsapp

NOME_FASE = {"base": "Base", "construcao": "Construção", "pico": "Pico", "polimento": "Polimento",
             "recuperacao": "Recuperação"}
DIA_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
ROTULO = {VERMELHO: "Atenção já", AMARELO: "Acompanhar", VERDE: "Tudo certo"}


@dataclass
class ItemRelatorio:
    atleta: Atleta
    resumo: ResumoSemana
    feedback: Feedback
    proxima: list[TreinoPrescrito]
    fase_proxima: str
    motivo: str
    erro: str | None = None


def _e(v: Any) -> str:
    return escape("" if v is None else str(v))


def _fmt(v: Any, suf: str = "", nd: str = "–") -> str:
    return nd if v is None else f"{v}{suf}"


def _card(i: int, it: ItemRelatorio) -> str:
    r, fb, a = it.resumo, it.feedback, it.atleta
    status = r.status
    kpis = [
        ("Horas", f"{r.horas_total}h"),
        ("Cumprimento", f"{r.cumprimento:.0%}" if r.cumprimento is not None else "–"),
        ("Carga", f"{r.carga_total}" + (f"/{r.carga_planejada}" if r.carga_planejada else "")),
        ("CTL", _fmt(r.ctl)),
        ("Forma (TSB)", _fmt(r.tsb)),
        ("Rampa", _fmt(r.rampa_ctl, "", "–") if r.rampa_ctl is None else f"{r.rampa_ctl:+}"),
        ("HRV", f"{_fmt(r.hrv_media)}" + (f" <small>/ {r.hrv_base}</small>" if r.hrv_base else "")),
        ("Sono", _fmt(r.sono_medio_h, "h")),
    ]
    kpi_html = "".join(f'<div class="kpi"><span>{k}</span><b>{v}</b></div>' for k, v in kpis)

    esportes = "".join(
        f"<tr><td>{NOME_ESPORTE[e]}</td><td>{s['sessoes']:.0f}</td><td>{s['horas']:.1f}h</td>"
        f"<td>{s['km']} km</td><td>{s['carga']:.0f}</td></tr>"
        for e, s in sorted(r.por_esporte.items()))
    alertas = "".join(f'<li class="al-{x.nivel}">{_e(x.texto)}</li>' for x in r.alertas) \
        or '<li class="al-verde">Nenhum alerta</li>'
    perdidos = (f'<p class="muted">Não realizados: {_e(", ".join(r.treinos_perdidos))}</p>'
                if r.treinos_perdidos else "")
    ajustes = "".join(f"<li>{_e(x)}</li>" for x in fb.ajustes_sugeridos)
    nomes_treinos = {t.id: f"{t.data[8:10]}/{t.data[5:7]} {t.nome}" for t in r.treinos}
    comentarios = "".join(
        f'<div class="coment"><div class="muted">{_e(nomes_treinos.get(c["id"], c["id"]))}</div>'
        f'<p>{_e(c["texto"])}</p><button class="btn sec" data-copy="{_e(c["texto"])}">Copiar</button></div>'
        for c in fb.comentarios_treinos)
    feitos = "".join(
        f"<tr><td>{t.data[8:10]}/{t.data[5:7]}</td><td>{_e(t.nome)}</td><td>{t.duracao_min}′</td>"
        f"<td>{t.carga:.0f}</td><td>{_fmt(t.rpe)}</td><td class='muted'>{_e(t.comentario[:80])}</td></tr>"
        for t in r.treinos)
    proxima = "".join(
        f"<details class='treino'><summary><b>{DIA_SEMANA[t.data.weekday()]} {t.data.strftime('%d/%m')}</b> "
        f"{_e(t.nome)} <span class='muted'>~{t.duracao_min}′</span></summary><pre>{_e(t.descricao)}</pre></details>"
        for t in it.proxima)
    horas_prox = round(sum(t.duracao_min for t in it.proxima) / 60, 1)
    prova = (f"{_e(a.prova_alvo.nome)} · {r.semanas_para_prova} sem" if a.prova_alvo and r.semanas_para_prova is not None
             else "Sem prova alvo")
    link = link_whatsapp(a.whatsapp, fb.whatsapp) if a.whatsapp else ""
    erro = f'<p class="al-vermelho">Erro ao buscar dados: {_e(it.erro)}</p>' if it.erro else ""

    return f"""
<article class="card st-{status}" data-status="{status}" id="a{i}">
  <header>
    <div><h2>{_e(a.nome)}</h2><div class="muted">{NOME_FASE.get(r.fase, r.fase)} · {prova}</div></div>
    <div class="right"><span class="pill pill-{status}">{ROTULO[status]}</span>
      <label class="feito"><input type="checkbox" data-key="{_e(a.slug)}"> feito</label></div>
  </header>
  {erro}
  <ul class="alertas">{alertas}</ul>
  <div class="kpis">{kpi_html}</div>
  <section class="grid2">
    <div>
      <h3>Mensagem WhatsApp <small class="muted">({'IA' if fb.gerado_por == 'ia' else 'modelo'} · edite à vontade)</small></h3>
      <textarea data-phone="{_e(a.whatsapp)}" rows="8">{_e(fb.whatsapp)}</textarea>
      <div class="acoes">
        {'<a class="btn wa" target="_blank" rel="noopener" href="' + _e(link) + '">Abrir no WhatsApp</a>' if link else '<span class="muted">Sem telefone cadastrado</span>'}
        <button class="btn sec" data-copy-from="textarea">Copiar</button>
      </div>
    </div>
    <div>
      <h3>Notas para você</h3>
      <p class="notas">{_e(fb.notas_treinador)}</p>
      {f'<h3>Ajustes sugeridos</h3><ul>{ajustes}</ul>' if ajustes else ''}
    </div>
  </section>
  {f'<h3>Comentários para os treinos <small class="muted">(TrainingPeaks / intervals.icu)</small></h3><div class="coments">{comentarios}</div>' if comentarios else ''}
  <details><summary>Semana realizada: {len(r.treinos)} treinos</summary>
    {perdidos}
    <table><tr><th>Esporte</th><th>Sessões</th><th>Horas</th><th>Distância</th><th>Carga</th></tr>{esportes}</table>
    <table class="feitos"><tr><th>Dia</th><th>Treino</th><th>Tempo</th><th>Carga</th><th>RPE</th><th>Comentário</th></tr>{feitos}</table>
  </details>
  <details><summary>Próxima semana: {NOME_FASE.get(it.fase_proxima, it.fase_proxima)} · {len(it.proxima)} treinos · ~{horas_prox}h <span class="muted">({_e(it.motivo)})</span></summary>
    {proxima}
  </details>
</article>"""


def gerar_html(itens: list[ItemRelatorio], semana_analisada: date, semana_prescrita: date,
               treinador: str = "", equipe: str = "") -> str:
    ordem = {VERMELHO: 0, AMARELO: 1, VERDE: 2}
    itens = sorted(itens, key=lambda x: (ordem[x.resumo.status], x.atleta.nome))
    cont = {s: sum(1 for x in itens if x.resumo.status == s) for s in ordem}
    horas = round(sum(x.resumo.horas_total for x in itens), 1)
    cards = "".join(_card(i, it) for i, it in enumerate(itens))
    chave_semana = semana_analisada.isoformat()
    titulo = f"Semana {semana_analisada.strftime('%d/%m')}"
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(equipe or 'DG Endurance')} · {titulo}</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--tx:#1d2330;--mu:#6b7280;--bd:#e5e7eb;--vm:#dc2626;--am:#d97706;--vd:#16a34a;--ac:#2563eb;--wa:#16a34a;--soft:#f3f4f6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0f1115;--card:#181b22;--tx:#e8eaf0;--mu:#9aa1ad;--bd:#2a2f3a;--soft:#20242d}}}}
:root[data-theme="dark"]{{--bg:#0f1115;--card:#181b22;--tx:#e8eaf0;--mu:#9aa1ad;--bd:#2a2f3a;--soft:#20242d}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:16px}}
h1{{font-size:22px;margin:4px 0}} h2{{font-size:18px;margin:0}} h3{{font-size:14px;margin:14px 0 6px;text-transform:uppercase;letter-spacing:.03em;color:var(--mu)}}
.muted{{color:var(--mu);font-size:13px}} small{{font-weight:400}}
.resumo{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}
.resumo button{{border:1px solid var(--bd);background:var(--card);color:var(--tx);border-radius:999px;padding:6px 12px;cursor:pointer;font:inherit}}
.resumo button.on{{outline:2px solid var(--ac)}}
.card{{background:var(--card);border:1px solid var(--bd);border-left:5px solid var(--vd);border-radius:12px;padding:16px;margin:14px 0}}
.st-vermelho{{border-left-color:var(--vm)}} .st-amarelo{{border-left-color:var(--am)}}
.card.done{{opacity:.55}}
header{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}} .right{{text-align:right}}
.pill{{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;color:#fff}}
.pill-vermelho{{background:var(--vm)}} .pill-amarelo{{background:var(--am)}} .pill-verde{{background:var(--vd)}}
.feito{{display:block;margin-top:6px;font-size:13px;color:var(--mu)}}
.alertas{{list-style:none;padding:0;margin:10px 0}} .alertas li{{padding:4px 8px;border-radius:6px;margin:3px 0;font-size:14px;background:var(--soft)}}
.al-vermelho{{color:var(--vm);font-weight:600}} .al-amarelo{{color:var(--am)}} .al-verde{{color:var(--vd)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:8px;margin:10px 0}}
.kpi{{background:var(--soft);border-radius:8px;padding:8px}} .kpi span{{display:block;font-size:12px;color:var(--mu)}} .kpi b{{font-size:17px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media (max-width:760px){{.grid2{{grid-template-columns:1fr}} header{{flex-direction:column}} .right{{text-align:left;display:flex;gap:12px;align-items:center}} .feito{{margin:0}} .kpis{{grid-template-columns:repeat(3,1fr)}}}}
textarea{{width:100%;font:inherit;padding:10px;border-radius:8px;border:1px solid var(--bd);background:var(--soft);color:var(--tx);resize:vertical}}
.acoes{{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}}
.btn{{border:0;border-radius:8px;padding:8px 14px;font:inherit;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}}
.btn.wa{{background:var(--wa);color:#fff}} .btn.sec{{background:var(--soft);color:var(--tx);border:1px solid var(--bd)}}
.notas{{white-space:pre-wrap;background:var(--soft);padding:10px;border-radius:8px;margin:0}}
.coments{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}}
.coment{{background:var(--soft);border-radius:8px;padding:10px}} .coment p{{margin:4px 0 8px}}
details{{margin-top:10px;border-top:1px solid var(--bd);padding-top:8px}} summary{{cursor:pointer;font-weight:600}}
details.treino{{border:0;padding:4px 0;margin:0}} details.treino summary{{font-weight:400}}
pre{{background:var(--soft);padding:10px;border-radius:8px;white-space:pre-wrap;font-size:13px}}
table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:14px;display:block;overflow-x:auto}}
th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid var(--bd)}}
</style></head><body><div class="wrap">
<div class="muted">{_e(equipe)} · {_e(treinador)}</div>
<h1>Revisão da semana {semana_analisada.strftime('%d/%m')} a {(semana_analisada + timedelta(days=6)).strftime('%d/%m')}</h1>
<div class="muted">{len(itens)} atletas · {horas}h treinadas no total · prescrição pronta para a semana de {semana_prescrita.strftime('%d/%m')}</div>
<div class="resumo">
  <button data-f="todos" class="on">Todos ({len(itens)})</button>
  <button data-f="vermelho">🔴 Atenção já ({cont[VERMELHO]})</button>
  <button data-f="amarelo">🟡 Acompanhar ({cont[AMARELO]})</button>
  <button data-f="verde">🟢 Tudo certo ({cont[VERDE]})</button>
  <button data-f="pendente">Pendentes</button>
</div>
{cards}
<p class="muted">Gerado automaticamente. Revise antes de enviar: você é o treinador, a IA só faz o rascunho.</p>
</div>
<script>
(function(){{
  var SEM = "{chave_semana}";
  function ler(k){{ try {{ return localStorage.getItem("dg:"+SEM+":"+k); }} catch(e) {{ return null; }} }}
  function gravar(k,v){{ try {{ localStorage.setItem("dg:"+SEM+":"+k, v); }} catch(e) {{}} }}
  function copiar(t, b){{
    var ok=function(){{ var o=b.textContent; b.textContent="Copiado ✓"; setTimeout(function(){{b.textContent=o;}},1500); }};
    if (navigator.clipboard) navigator.clipboard.writeText(t).then(ok, function(){{}});
  }}
  document.querySelectorAll(".card").forEach(function(card){{
    var cb = card.querySelector("input[type=checkbox]");
    var ta = card.querySelector("textarea");
    var wa = card.querySelector("a.wa");
    if (cb) {{ cb.checked = ler(cb.dataset.key) === "1"; card.classList.toggle("done", cb.checked);
      cb.addEventListener("change", function(){{ gravar(cb.dataset.key, cb.checked?"1":"0"); card.classList.toggle("done", cb.checked); }}); }}
    if (ta && wa) {{
      var salvo = cb && ler(cb.dataset.key+":msg"); if (salvo) ta.value = salvo;
      var upd = function(){{ wa.href = "https://wa.me/" + ta.dataset.phone + "?text=" + encodeURIComponent(ta.value); }};
      upd(); ta.addEventListener("input", function(){{ upd(); if (cb) gravar(cb.dataset.key+":msg", ta.value); }});
    }}
    card.querySelectorAll("[data-copy]").forEach(function(b){{ b.addEventListener("click", function(){{ copiar(b.dataset.copy, b); }}); }});
    card.querySelectorAll("[data-copy-from]").forEach(function(b){{ b.addEventListener("click", function(){{ copiar(ta.value, b); }}); }});
  }});
  document.querySelectorAll(".resumo button").forEach(function(b){{
    b.addEventListener("click", function(){{
      document.querySelectorAll(".resumo button").forEach(function(x){{ x.classList.remove("on"); }}); b.classList.add("on");
      var f = b.dataset.f;
      document.querySelectorAll(".card").forEach(function(c){{
        var show = f==="todos" || c.dataset.status===f || (f==="pendente" && !c.classList.contains("done"));
        c.style.display = show ? "" : "none";
      }});
    }});
  }});
}})();
</script></body></html>"""
