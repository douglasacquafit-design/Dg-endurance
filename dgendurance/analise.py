"""Análise semanal de cada atleta: volume, carga, cumprimento do plano, forma e alertas."""
from __future__ import annotations

import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .config import Atleta, Config

ESPORTES = {
    "bike": {"Ride", "VirtualRide", "MountainBikeRide", "GravelRide", "EBikeRide", "Velomobile"},
    "corrida": {"Run", "VirtualRun", "TrailRun"},
    "natacao": {"Swim", "OpenWaterSwim"},
    "forca": {"WeightTraining", "Workout", "Crossfit", "Yoga", "Pilates"},
}
NOME_ESPORTE = {"bike": "Pedal", "corrida": "Corrida", "natacao": "Natação", "forca": "Força", "outros": "Outros"}
VERMELHO, AMARELO, VERDE = "vermelho", "amarelo", "verde"
_ORDEM = {VERMELHO: 0, AMARELO: 1, VERDE: 2}


def esporte_de(tipo: str | None) -> str:
    for nome, tipos in ESPORTES.items():
        if tipo in tipos:
            return nome
    return "outros"


def _data(valor: Any) -> date | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "")).date()
    except ValueError:
        return None


def inicio_semana(d: date) -> date:
    return d - timedelta(days=d.weekday())


def fase_treino(atleta: Atleta, semana: date) -> tuple[str, int | None]:
    """Fase do ciclo pela distância (em semanas) até a prova alvo."""
    if not atleta.prova_alvo or atleta.prova_alvo.data < semana:
        return "base", None
    semanas = (atleta.prova_alvo.data - semana).days // 7
    if semanas > 16:
        return "base", semanas
    if semanas >= 8:
        return "construcao", semanas
    if semanas >= 3:
        return "pico", semanas
    return "polimento", semanas


@dataclass
class Alerta:
    nivel: str
    texto: str
    # fadiga | dor | cumprimento | bem_estar | intensidade
    categoria: str = "fadiga"


@dataclass
class TreinoRealizado:
    id: str
    data: str
    esporte: str
    nome: str
    duracao_min: int
    distancia_km: float
    carga: float
    intensidade: float | None
    fc_media: float | None
    potencia_norm: float | None
    rpe: float | None
    sensacao: int | None
    comentario: str
    planejado_tipo: str | None = None


@dataclass
class ResumoSemana:
    atleta: str
    inicio: str
    fim: str
    fase: str
    semanas_para_prova: int | None
    prova: str | None
    por_esporte: dict[str, dict[str, float]]
    horas_total: float
    carga_total: float
    carga_planejada: float
    treinos_planejados: int
    treinos_cumpridos: int
    cumprimento: float | None
    treinos_perdidos: list[str]
    ctl: float | None
    atl: float | None
    tsb: float | None
    rampa_ctl: float | None
    distribuicao_fc: dict[str, float]
    hrv_media: float | None
    hrv_base: float | None
    fc_repouso_media: float | None
    sono_medio_h: float | None
    dias_sem_treinar: int
    treinos: list[TreinoRealizado]
    alertas: list[Alerta] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.alertas:
            return VERDE
        return min((a.nivel for a in self.alertas), key=lambda n: _ORDEM[n])

    def para_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status
        return d


def _media(valores: list[float]) -> float | None:
    valores = [v for v in valores if v is not None]
    return round(statistics.fmean(valores), 1) if valores else None


def _mesmo_esporte(planejado: dict[str, Any], atividade: dict[str, Any]) -> bool:
    return esporte_de(planejado.get("type")) == esporte_de(atividade.get("type"))


def analisar_semana(atleta: Atleta, dados: dict[str, Any], inicio: date, cfg: Config) -> ResumoSemana:
    lim = cfg.alertas
    fim = inicio + timedelta(days=6)
    todas = sorted(dados.get("atividades", []), key=lambda a: str(a.get("start_date_local", "")))
    semana = [a for a in todas if (d := _data(a.get("start_date_local"))) and inicio <= d <= fim]
    planejados = [e for e in dados.get("planejados", [])
                  if (d := _data(e.get("start_date_local"))) and inicio <= d <= fim]
    bem_estar = {str(w.get("id")): w for w in dados.get("bem_estar", [])}

    # ---------- cumprimento: planejado x realizado ----------
    usados: set[str] = set()
    tipo_planejado: dict[str, str] = {}
    perdidos: list[str] = []
    for p in planejados:
        pid = str(p.get("id"))
        dia = _data(p.get("start_date_local"))
        par = next((a for a in semana if str(a.get("paired_event_id")) == pid and str(a.get("id")) not in usados), None)
        if par is None:
            par = next((a for a in semana if str(a.get("id")) not in usados
                        and _data(a.get("start_date_local")) == dia and _mesmo_esporte(p, a)), None)
        if par is None:
            perdidos.append(f"{dia.strftime('%d/%m') if dia else '?'} {p.get('name') or p.get('type')}")
        else:
            usados.add(str(par.get("id")))
            tipo_planejado[str(par.get("id"))] = _tipo_treino(p, cfg)
    cumpridos = len(planejados) - len(perdidos)
    cumprimento = round(cumpridos / len(planejados), 2) if planejados else None
    carga_planejada = sum(float(p.get("icu_training_load") or p.get("load_target") or 0) for p in planejados)

    # ---------- volume ----------
    por_esporte: dict[str, dict[str, float]] = {}
    treinos: list[TreinoRealizado] = []
    zonas = [0.0] * 7
    for a in semana:
        esp = esporte_de(a.get("type"))
        s = por_esporte.setdefault(esp, {"sessoes": 0, "horas": 0.0, "km": 0.0, "carga": 0.0})
        mov = float(a.get("moving_time") or 0)
        s["sessoes"] += 1
        s["horas"] = round(s["horas"] + mov / 3600, 2)
        s["km"] = round(s["km"] + float(a.get("distance") or 0) / 1000, 1)
        s["carga"] = round(s["carga"] + float(a.get("icu_training_load") or 0), 0)
        for i, seg in enumerate((a.get("icu_hr_zone_times") or [])[:7]):
            zonas[i] += float(seg or 0)
        treinos.append(TreinoRealizado(
            id=str(a.get("id")),
            data=str(a.get("start_date_local", ""))[:10],
            esporte=esp,
            nome=a.get("name") or NOME_ESPORTE[esp],
            duracao_min=round(mov / 60),
            distancia_km=round(float(a.get("distance") or 0) / 1000, 2),
            carga=float(a.get("icu_training_load") or 0),
            intensidade=a.get("icu_intensity"),
            fc_media=a.get("average_heartrate"),
            potencia_norm=a.get("icu_weighted_avg_watts"),
            rpe=a.get("icu_rpe") or a.get("perceived_exertion"),
            sensacao=a.get("feel"),
            comentario=(a.get("description") or "").strip(),
            planejado_tipo=tipo_planejado.get(str(a.get("id"))),
        ))
    total_z = sum(zonas)
    dist_fc = {}
    if total_z > 0:
        dist_fc = {
            "z1_z2": round((zonas[0] + zonas[1]) / total_z, 2),
            "z3": round(zonas[2] / total_z, 2),
            "z4_mais": round(sum(zonas[3:]) / total_z, 2),
        }

    # ---------- forma (CTL/ATL/TSB) ----------
    def bw(d: date) -> dict[str, Any]:
        return bem_estar.get(d.isoformat(), {})

    ctl, atl = bw(fim).get("ctl"), bw(fim).get("atl")
    ctl_ini = bw(inicio - timedelta(days=1)).get("ctl")
    tsb = round(ctl - atl, 1) if ctl is not None and atl is not None else None
    rampa = round(ctl - ctl_ini, 1) if ctl is not None and ctl_ini is not None else None

    # ---------- bem-estar ----------
    dias_semana = [inicio + timedelta(days=i) for i in range(7)]
    dias_base = [inicio - timedelta(days=i) for i in range(1, 29)]
    hrv_semana = _media([bw(d).get("hrv") for d in dias_semana])
    hrv_base = _media([bw(d).get("hrv") for d in dias_base])
    fc_rep = _media([bw(d).get("restingHR") for d in dias_semana])
    sono = _media([(bw(d).get("sleepSecs") or 0) / 3600 or None for d in dias_semana])

    # dias seguidos sem treinar até o fim da semana
    datas_ativ = {_data(a.get("start_date_local")) for a in todas}
    sem_treinar = 0
    d = fim
    while d not in datas_ativ and sem_treinar < 28:
        sem_treinar += 1
        d -= timedelta(days=1)

    fase, semanas_prova = fase_treino(atleta, inicio)
    resumo = ResumoSemana(
        atleta=atleta.nome, inicio=inicio.isoformat(), fim=fim.isoformat(),
        fase=fase, semanas_para_prova=semanas_prova,
        prova=atleta.prova_alvo.nome if atleta.prova_alvo else None,
        por_esporte=por_esporte,
        horas_total=round(sum(s["horas"] for s in por_esporte.values()), 1),
        carga_total=round(sum(s["carga"] for s in por_esporte.values())),
        carga_planejada=round(carga_planejada),
        treinos_planejados=len(planejados), treinos_cumpridos=cumpridos,
        cumprimento=cumprimento, treinos_perdidos=perdidos,
        ctl=ctl, atl=atl, tsb=tsb, rampa_ctl=rampa, distribuicao_fc=dist_fc,
        hrv_media=hrv_semana, hrv_base=hrv_base, fc_repouso_media=fc_rep, sono_medio_h=sono,
        dias_sem_treinar=sem_treinar, treinos=treinos,
    )
    resumo.alertas = gerar_alertas(resumo, lim)
    return resumo


def _tipo_treino(planejado: dict[str, Any], cfg: Config) -> str | None:
    """Tipo (leve/chave/longo...) de um treino planejado que veio da nossa biblioteca."""
    ext = str(planejado.get("external_id") or "")
    for chave, t in cfg.treinos.items():
        if ext.endswith(f"-{chave}"):
            return t.get("tipo")
    return None


def _contem(texto: str, palavras: list[str]) -> str | None:
    """Procura palavras pelo início (\"machuc\" acha \"machucou\"). Palavras curtas
    (até 4 letras, ex. \"dor\") precisam ser a palavra inteira, para \"dormi\" não virar \"dor\"."""
    t = texto.lower()
    for p in palavras:
        p = p.lower().strip()
        fim = r"\b" if len(p) <= 4 else ""
        if re.search(r"\b" + re.escape(p) + fim, t):
            return p
    return None


def gerar_alertas(r: ResumoSemana, lim: dict[str, Any]) -> list[Alerta]:
    al: list[Alerta] = []

    if r.tsb is not None:
        if r.tsb <= lim.get("tsb_vermelho", -30):
            al.append(Alerta(VERMELHO, f"Fadiga muito alta: forma (TSB) em {r.tsb}", "fadiga"))
        elif r.tsb <= lim.get("tsb_amarelo", -20):
            al.append(Alerta(AMARELO, f"Fadiga acumulando: forma (TSB) em {r.tsb}", "fadiga"))

    if r.rampa_ctl is not None:
        if r.rampa_ctl >= lim.get("rampa_vermelho", 8):
            al.append(Alerta(VERMELHO, f"Carga subiu rápido demais: CTL +{r.rampa_ctl} na semana", "fadiga"))
        elif r.rampa_ctl >= lim.get("rampa_amarelo", 5):
            al.append(Alerta(AMARELO, f"Rampa de carga alta: CTL +{r.rampa_ctl} na semana", "fadiga"))

    if r.cumprimento is not None:
        pct = f"{r.cumprimento:.0%} ({r.treinos_cumpridos}/{r.treinos_planejados})"
        if r.cumprimento < lim.get("cumprimento_vermelho", 0.5):
            al.append(Alerta(VERMELHO, f"Cumpriu só {pct} dos treinos", "cumprimento"))
        elif r.cumprimento < lim.get("cumprimento_amarelo", 0.75):
            al.append(Alerta(AMARELO, f"Cumprimento baixo: {pct}", "cumprimento"))

    if r.dias_sem_treinar >= lim.get("dias_sem_treinar", 4):
        al.append(Alerta(VERMELHO, f"Sem registrar treino há {r.dias_sem_treinar} dias", "cumprimento"))

    if r.hrv_media and r.hrv_base and r.hrv_media < r.hrv_base * (1 - lim.get("queda_hrv", 0.12)):
        queda = 1 - r.hrv_media / r.hrv_base
        al.append(Alerta(AMARELO, f"HRV {queda:.0%} abaixo da média de 4 semanas ({r.hrv_media} vs {r.hrv_base})",
                         "bem_estar"))

    if r.sono_medio_h and r.sono_medio_h < lim.get("sono_minimo_h", 6.0):
        al.append(Alerta(AMARELO, f"Dormindo pouco: média de {r.sono_medio_h}h", "bem_estar"))

    dor, cansaco, leve_forte, sensacao = [], [], [], []
    for t in r.treinos:
        dia = f"{t.data[8:10]}/{t.data[5:7]}"
        if t.comentario:
            if _contem(t.comentario, lim.get("palavras_dor", [])):
                dor.append(f"{dia} ({t.nome}): \"{t.comentario[:140]}\"")
            elif _contem(t.comentario, lim.get("palavras_cansaco", [])):
                cansaco.append(f"{dia}: \"{t.comentario[:80]}\"")
        if (t.planejado_tipo in ("leve", "recuperacao") and t.rpe
                and t.rpe >= lim.get("rpe_alto_treino_leve", 7)):
            leve_forte.append(f"{dia} {t.nome} (RPE {t.rpe:g})")
        if t.sensacao and t.sensacao >= 5:  # intervals.icu: 1 = muito bem ... 5 = muito mal
            sensacao.append(f"{dia} {t.nome}")

    for x in dor:
        al.append(Alerta(VERMELHO, f"Relato de dor/lesão em {x}", "dor"))
    if cansaco:
        extra = f" (+{len(cansaco) - 2})" if len(cansaco) > 2 else ""
        al.append(Alerta(AMARELO, f"Relatos de cansaço/doença em {len(cansaco)} treinos: "
                         + "; ".join(cansaco[:2]) + extra, "bem_estar"))
    if leve_forte:
        al.append(Alerta(AMARELO, f"{len(leve_forte)} treino(s) leve(s) feito(s) forte demais: "
                         + ", ".join(leve_forte), "intensidade"))
    if sensacao:
        al.append(Alerta(AMARELO, "Sensação ruim em: " + ", ".join(sensacao), "bem_estar"))

    dist = r.distribuicao_fc
    if dist:
        if dist.get("z1_z2", 1) < lim.get("leve_minimo", 0.75):
            al.append(Alerta(AMARELO, f"Só {dist['z1_z2']:.0%} do tempo em Z1-Z2 (alvo 80/20): "
                             f"Z3 {dist.get('z3', 0):.0%}, Z4+ {dist.get('z4_mais', 0):.0%}", "intensidade"))
        elif dist.get("z3", 0) > lim.get("z3_maximo", 0.15) and r.fase in ("base", "construcao"):
            al.append(Alerta(AMARELO, f"{dist['z3']:.0%} do tempo na Z3 (zona cinzenta): leve não está leve",
                             "intensidade"))

    al.sort(key=lambda a: _ORDEM[a.nivel])
    return al
