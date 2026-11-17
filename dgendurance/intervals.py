"""Cliente da API do intervals.icu.

Documentação: https://intervals.icu/api-docs.html
Autenticação: usuário "API_KEY" + sua chave (Configurações > Developer Settings).
Como treinador, sua chave acessa os atletas que compartilharam a conta com você.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Any

import requests

BASE_URL = "https://intervals.icu/api/v1"


class IntervalsErro(RuntimeError):
    pass


class IntervalsClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: int = 30):
        if not api_key:
            raise IntervalsErro("INTERVALS_API_KEY não configurada (veja o README).")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sessao = requests.Session()
        self.sessao.auth = ("API_KEY", api_key)
        self.sessao.headers["Accept"] = "application/json"

    def _req(self, metodo: str, caminho: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{caminho}"
        for tentativa in range(4):
            resp = self.sessao.request(metodo, url, timeout=self.timeout, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** tentativa)
                continue
            break
        if resp.status_code == 401:
            raise IntervalsErro("Chave do intervals.icu inválida (401).")
        if resp.status_code == 403:
            raise IntervalsErro(f"Sem permissão para {caminho} (403). O atleta compartilhou a conta com você?")
        if not resp.ok:
            raise IntervalsErro(f"Erro {resp.status_code} em {metodo} {caminho}: {resp.text[:300]}")
        return resp.json() if resp.content else None

    @staticmethod
    def _periodo(inicio: date, fim: date) -> dict[str, str]:
        return {"oldest": inicio.isoformat(), "newest": fim.isoformat()}

    # ---------------- leitura ----------------
    def atleta(self, athlete_id: str = "0") -> dict[str, Any]:
        return self._req("GET", f"/athlete/{athlete_id}")

    def atividades(self, athlete_id: str, inicio: date, fim: date) -> list[dict[str, Any]]:
        return self._req("GET", f"/athlete/{athlete_id}/activities", params=self._periodo(inicio, fim)) or []

    def bem_estar(self, athlete_id: str, inicio: date, fim: date) -> list[dict[str, Any]]:
        """Wellness: CTL, ATL, HRV, FC repouso, sono, fadiga, dor muscular..."""
        return self._req("GET", f"/athlete/{athlete_id}/wellness", params=self._periodo(inicio, fim)) or []

    def eventos(self, athlete_id: str, inicio: date, fim: date) -> list[dict[str, Any]]:
        """Treinos planejados no calendário."""
        params = self._periodo(inicio, fim) | {"category": "WORKOUT"}
        return self._req("GET", f"/athlete/{athlete_id}/events", params=params) or []

    # ---------------- escrita ----------------
    def gravar_treinos(self, athlete_id: str, eventos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Cria/atualiza treinos no calendário. 'external_id' evita duplicar se rodar de novo."""
        return self._req("POST", f"/athlete/{athlete_id}/events/bulk", params={"upsert": "true"}, json=eventos) or []

    def comentar_atividade(self, activity_id: str, texto: str) -> Any:
        """Publica um comentário na atividade (aparece para o atleta no intervals.icu)."""
        return self._req("POST", f"/activity/{activity_id}/messages", json={"content": texto})


class FonteIntervals:
    """Fonte de dados real: busca tudo que a análise precisa de um atleta."""

    def __init__(self, cliente: IntervalsClient):
        self.cliente = cliente

    def dados_atleta(self, athlete_id: str, inicio: date, fim: date, inicio_historico: date) -> dict[str, Any]:
        return {
            "atividades": self.cliente.atividades(athlete_id, inicio_historico, fim),
            "bem_estar": self.cliente.bem_estar(athlete_id, inicio_historico, fim),
            "planejados": self.cliente.eventos(athlete_id, inicio, fim),
        }
