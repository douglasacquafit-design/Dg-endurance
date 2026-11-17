"""Dados fictícios no formato do intervals.icu, para testar sem conectar contas."""
from __future__ import annotations

import copy
import random
from datetime import date, timedelta
from typing import Any

from .config import Atleta, Config, ProvaAlvo

ATLETAS_DEMO = [
    # (atleta, cenário)
    (Atleta("Ana Souza", "demo1", "5511999990001", "intermediario", 1.0,
            ProvaAlvo("Ironman 70.3 Florianópolis", date(2027, 4, 18), "70.3"), ["seg"],
            "Professora, treina cedo. Histórico de canelite em 2025."), "perfeita"),
    (Atleta("Bruno Lima", "demo2", "5511999990002", "avancado", 1.2,
            ProvaAlvo("Ironman Brasil", date(2027, 5, 30), "140.6"), [],
            "Ex-nadador. Tende a exagerar na intensidade."), "exagero"),
    (Atleta("Carla Mendes", "demo3", "5511999990003", "iniciante", 1.0,
            ProvaAlvo("Triathlon Olímpico Santos", date(2027, 3, 7), "olimpico"), ["seg", "qua"],
            "Médica plantonista, agenda imprevisível.", ciclo="2:1"), "faltas"),
    (Atleta("Diego Rocha", "demo4", "5511999990004", "intermediario", 1.0,
            ProvaAlvo("Ironman 70.3 Rio", date(2027, 2, 14), "70.3"), ["seg"],
            "Corredor de origem, nada mal."), "dor"),
    (Atleta("Elisa Prado", "demo5", "5511999990005", "avancado", 1.1,
            ProvaAlvo("Ironman 70.3 Florianópolis", date(2027, 4, 18), "70.3"), [],
            "Bebê de 6 meses em casa."), "fadiga"),
    (Atleta("Felipe Torres", "demo6", "5511999990006", "intermediario", 0.9, None, ["seg"],
            "Sem prova definida, treina por saúde."), "sumido"),
]

_CARGA_POR_MIN = {"recuperacao": 0.45, "leve": 0.7, "longo": 0.8, "chave": 1.15, "forca": 0.4, "": 0.7}
_TIPO_ATIVIDADE = {"Ride": ["Ride", "VirtualRide"], "Run": ["Run"], "Swim": ["Swim"],
                   "WeightTraining": ["WeightTraining"]}
_COMENTARIOS_OK = ["Treino top, me senti bem!", "Pernas boas hoje.", "", "", "Calor forte, mas deu certo."]


class FonteDemo:
    def __init__(self, cfg: Config, semana: date, seed: int = 7):
        import copy

        # No demo, o histórico usa só semanas de carga (sem recuperação programada)
        self.cfg = copy.copy(cfg)
        self.cfg.geral = dict(cfg.geral, ciclo_padrao="livre")
        self.semana = semana
        self.seed = seed
        self.cenarios = {a.intervals_id: c for a, c in ATLETAS_DEMO}
        self.atletas = {a.intervals_id: a for a, _ in ATLETAS_DEMO}

    def dados_atleta(self, athlete_id: str, inicio: date, fim: date, inicio_historico: date) -> dict[str, Any]:
        from .prescricao import montar_semana

        rnd = random.Random(f"{self.seed}-{athlete_id}")
        atleta = self.atletas[athlete_id]
        cenario = self.cenarios[athlete_id]
        atleta_hist = copy.copy(atleta)
        atleta_hist.ciclo = "livre"
        planejados_semana, _, _ = montar_semana(atleta_hist, inicio, self.cfg)

        planejados = []
        for i, t in enumerate(planejados_semana):
            ev = t.evento_intervals(atleta)
            ev |= {"id": f"{athlete_id}-ev{i}",
                   "icu_training_load": round(t.duracao_min * _CARGA_POR_MIN.get(t.tipo, 0.7))}
            planejados.append((t, ev))

        atividades: list[dict[str, Any]] = []
        n = 0

        def nova(dia: date, tipo: str, nome: str, minutos: int, carga: float, tipo_treino: str,
                 evento: str | None = None, comentario: str = "", rpe: float | None = None,
                 z3_extra: float = 0.0) -> None:
            nonlocal n
            n += 1
            seg = minutos * 60
            if tipo_treino in ("leve", "recuperacao", "longo"):
                zonas = [0.35, 0.5 - z3_extra, 0.12 + z3_extra, 0.03, 0, 0, 0]
            else:
                zonas = [0.25, 0.3, 0.15, 0.2, 0.1, 0, 0]
            vel = {"Ride": 8.3, "VirtualRide": 8.6, "Run": 2.9, "Swim": 0.75}.get(tipo, 0)
            atividades.append({
                "id": f"{athlete_id}-a{n}", "start_date_local": f"{dia.isoformat()}T06:30:00",
                "type": tipo, "name": nome, "moving_time": seg, "distance": round(seg * vel),
                "icu_training_load": round(carga), "icu_intensity": round(rnd.uniform(62, 88), 1),
                "average_heartrate": rnd.randint(128, 158), "paired_event_id": evento,
                "icu_weighted_avg_watts": rnd.randint(170, 240) if "Ride" in tipo else None,
                "icu_rpe": rpe or (rnd.randint(3, 5) if tipo_treino in ("leve", "recuperacao") else rnd.randint(6, 8)),
                "feel": rnd.choice([1, 2, 2, 3]), "description": comentario,
                "icu_hr_zone_times": [round(seg * z) for z in zonas],
            })

        # ---------------- semanas anteriores (histórico) ----------------
        intensidade_hist = {"sumido": 0.9}.get(cenario, 1.0)
        d = inicio_historico
        while d < inicio:
            semana_ant, _, _ = montar_semana(atleta_hist, d - timedelta(days=d.weekday()), self.cfg)
            for t in semana_ant:
                if t.data == d and rnd.random() < 0.85:
                    tipo = rnd.choice(_TIPO_ATIVIDADE.get(t.esporte, [t.esporte]))
                    mins = round(t.duracao_min * rnd.uniform(0.9, 1.1))
                    nova(d, tipo, t.nome, mins, mins * _CARGA_POR_MIN.get(t.tipo, 0.7) * intensidade_hist, t.tipo)
            d += timedelta(days=1)

        # ---------------- semana analisada ----------------
        perdidos = 0
        for t, ev in planejados:
            fazer = True
            comentario, rpe, z3, mult = rnd.choice(_COMENTARIOS_OK), None, 0.0, 1.0
            if cenario == "faltas" and t.esporte != "Swim":
                fazer = rnd.random() < 0.3
            if cenario == "sumido" and t.data >= inicio + timedelta(days=1):
                fazer = False
            if cenario == "exagero":
                mult = 1.5
                if t.tipo in ("leve", "recuperacao"):
                    rpe, z3 = 8, 0.3
                    comentario = "Puxei um pouco, estava me sentindo forte!"
            if cenario == "dor" and t.esporte == "Run" and t.tipo == "longo":
                comentario = "Senti uma dor na panturrilha esquerda a partir do km 8, terminei trotando."
            if cenario == "fadiga":
                comentario = rnd.choice(["Mal dormi essa noite, bebê acordou 4x.", "Pernas pesadas.", ""])
                if rnd.random() < 0.2:
                    fazer = False
            if not fazer:
                perdidos += 1
                continue
            tipo = rnd.choice(_TIPO_ATIVIDADE.get(t.esporte, [t.esporte]))
            mins = round(t.duracao_min * rnd.uniform(0.92, 1.08) * (1.1 if cenario == "exagero" else 1))
            nova(t.data, tipo, t.nome, mins, mins * _CARGA_POR_MIN.get(t.tipo, 0.7) * mult, t.tipo,
                 evento=ev["id"], comentario=comentario, rpe=rpe, z3_extra=z3)

        # ---------------- wellness (CTL/ATL calculados das cargas) ----------------
        carga_dia: dict[date, float] = {}
        for a in atividades:
            dia = date.fromisoformat(a["start_date_local"][:10])
            carga_dia[dia] = carga_dia.get(dia, 0) + a["icu_training_load"]
        dias_hist = max(1, (inicio - inicio_historico).days)
        ctl = sum(c for dia, c in carga_dia.items() if dia < inicio) / dias_hist
        atl = ctl
        bem_estar = []
        d = inicio_historico
        hrv_base = rnd.uniform(55, 75)
        while d <= fim:
            c = carga_dia.get(d, 0)
            ctl += (c - ctl) / 42
            atl += (c - atl) / 7
            na_semana = d >= inicio
            hrv = hrv_base * (0.8 if (cenario == "fadiga" and na_semana) else 1) * rnd.uniform(0.95, 1.05)
            sono = (5.2 if (cenario == "fadiga" and na_semana) else rnd.uniform(6.5, 8)) * 3600
            bem_estar.append({"id": d.isoformat(), "ctl": round(ctl, 1), "atl": round(atl, 1),
                              "hrv": round(hrv), "restingHR": rnd.randint(46, 54), "sleepSecs": round(sono)})
            d += timedelta(days=1)

        return {"atividades": atividades, "bem_estar": bem_estar, "planejados": [ev for _, ev in planejados]}
