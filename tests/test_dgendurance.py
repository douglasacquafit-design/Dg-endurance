import json
from datetime import date

import httpx2 as httpx  # cliente HTTP usado pelo SDK da Anthropic
import pytest

from dgendurance.analise import VERDE, VERMELHO, _contem, analisar_semana
from dgendurance.cli import main
from dgendurance.config import carregar_config
from dgendurance.demo import ATLETAS_DEMO, FonteDemo
from dgendurance.feedback import gerar_feedback_ia, gerar_feedback_modelo
from dgendurance.prescricao import _distribuir_folgas, escalar_passo, montar_semana, renderizar_treino

SEMANA = date(2026, 11, 9)


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


@pytest.fixture(scope="module")
def resumos(cfg):
    fonte = FonteDemo(cfg, SEMANA)
    out = {}
    for atleta, cenario in ATLETAS_DEMO:
        dados = fonte.dados_atleta(atleta.intervals_id, SEMANA, date(2026, 11, 15), date(2026, 9, 28))
        out[cenario] = (atleta, analisar_semana(atleta, dados, SEMANA, cfg))
    return out


# ---------------- prescrição ----------------
@pytest.mark.parametrize("passo,fator,esperado", [
    ("60m 65-75%", 1.5, "90m 65-75%"),
    ("60m 65-75%", 1.0, "60m 65-75%"),
    ("800mtr Z2 Pace", 1.3, "1050mtr Z2 Pace"),
    ("1m30s Z1 Pace", 2, "3m Z1 Pace"),
    ("6m 95-100% Pace", 0.75, "4m30s 95-100% Pace"),
    ("Educativos à escolha", 2, "Educativos à escolha"),
])
def test_escalar_passo(passo, fator, esperado):
    assert escalar_passo(passo, fator) == esperado


def test_renderizar_repeticoes_escalam(cfg):
    texto, minutos = renderizar_treino(cfg.treinos["bike_sweetspot"], 1.4)
    assert "Principal 4x" in texto  # 3 reps * 1.4 = 4
    assert "- 12m 88-93%" in texto
    assert "3x\n- 1m 100%" in texto  # repetição interna do aquecimento preservada
    assert 90 < minutos < 120


def test_folgas_movem_treinos():
    semana = {"seg": ["a"], "ter": ["b"], "qua": [], "qui": [], "sex": [], "sab": [], "dom": []}
    res = _distribuir_folgas(semana, ["seg"])
    assert res["seg"] == [] and "a" in res["qua"]


def test_todos_os_modelos_renderizam(cfg):
    for chave, t in cfg.treinos.items():
        texto, _ = renderizar_treino(t, 1.2)
        assert texto.strip(), chave


# ---------------- análise ----------------
def test_dor_nao_confunde_com_dormi():
    palavras = carregar_config().alertas["palavras_dor"]
    assert _contem("Mal dormi essa noite", palavras) is None
    assert _contem("Senti uma dor no joelho", palavras) == "dor"
    assert _contem("Acho que machuquei", palavras) == "machu"


def test_cenarios_demo(resumos, cfg):
    assert resumos["perfeita"][1].status == VERDE
    assert resumos["exagero"][1].status == VERMELHO
    assert any(a.categoria == "dor" for a in resumos["dor"][1].alertas)
    assert any(a.categoria == "bem_estar" for a in resumos["fadiga"][1].alertas)
    assert resumos["sumido"][1].horas_total == 0


def test_decisao_da_proxima_semana(resumos, cfg):
    prox = date(2026, 11, 23)
    atleta, r = resumos["dor"]
    _, fase, motivo = montar_semana(atleta, prox, cfg, r)
    assert fase == "recuperacao" and "dor" in motivo
    atleta, r = resumos["sumido"]
    _, fase, motivo = montar_semana(atleta, prox, cfg, r)
    assert fase != "recuperacao" and "retomar" in motivo


# ---------------- feedback ----------------
def test_feedback_modelo(resumos):
    atleta, r = resumos["dor"]
    fb = gerar_feedback_modelo(atleta, r, "semana de recuperação")
    assert "Diego" in fb.whatsapp and "dor" in fb.whatsapp.lower()


def test_feedback_ia_monta_requisicao_e_le_resposta(resumos, cfg):
    import anthropic

    capturado = {}
    resposta_modelo = {"whatsapp": "Fala, Bruno!", "comentarios_treinos": [{"id": "x", "texto": "Boa"}],
                       "notas_treinador": "TSB baixo", "ajustes_sugeridos": ["reduzir volume"]}

    def handler(req: httpx.Request) -> httpx.Response:
        capturado["body"] = json.loads(req.content)
        capturado["beta"] = req.headers.get("anthropic-beta", "")
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": json.dumps(resposta_modelo)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    cliente = anthropic.Anthropic(api_key="teste", base_url="http://teste.local",
                                  http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    atleta, r = resumos["exagero"]
    fb = gerar_feedback_ia(atleta, r, [], "recuperação", cfg, cliente=cliente)

    body = capturado["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in capturado["beta"]
    assert "Bruno Lima" in body["messages"][0]["content"]
    assert fb.gerado_por == "ia" and fb.whatsapp == "Fala, Bruno!"


# ---------------- ponta a ponta ----------------
def test_comando_semana_demo(tmp_path):
    main(["semana", "--demo", "--sem-ia", "--data", "2026-11-17", "--saida", str(tmp_path)])
    pasta = tmp_path / "2026-11-09"
    html = (pasta / "painel.html").read_text(encoding="utf-8")
    assert "Bruno Lima" in html and "wa.me/5511999990002" in html
    dados = json.loads((pasta / "semana.json").read_text(encoding="utf-8"))
    assert dados["semana_prescrita"] == "2026-11-23"
    ev = dados["atletas"][0]["proxima_semana"][0]
    assert ev["category"] == "WORKOUT" and ev["external_id"].startswith("dg-")
