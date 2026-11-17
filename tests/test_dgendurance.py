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
    pasta = tmp_path / "demo-2026-11-09"
    html = (pasta / "painel.html").read_text(encoding="utf-8")
    assert "Bruno Lima" in html and "wa.me/5511999990002" in html
    dados = json.loads((pasta / "semana.json").read_text(encoding="utf-8"))
    assert dados["semana_prescrita"] == "2026-11-23"
    ev = dados["atletas"][0]["proxima_semana"][0]
    assert ev["category"] == "WORKOUT" and ev["external_id"].startswith("dg-")


# ---------------- ciclos, 80/20 e importação ----------------
def test_ciclo_por_atleta(cfg):
    from dgendurance.config import ProvaAlvo, Atleta, semanas_do_ciclo

    assert semanas_do_ciclo("3:1") == 4 and semanas_do_ciclo("2:1") == 3 and semanas_do_ciclo("livre") == 0
    prova = ProvaAlvo("p", date(2027, 6, 6), "70.3")
    fases = {}
    for ciclo in ("2:1", "3:1", "livre"):
        a = Atleta("X", "i1", ciclo=ciclo, prova_alvo=prova)
        semanas = [date(2026, 11, 23) + i * __import__("datetime").timedelta(days=7) for i in range(12)]
        fases[ciclo] = sum(montar_semana(a, s, cfg)[1] == "recuperacao" for s in semanas)
    assert fases["2:1"] == 4 and fases["3:1"] == 3 and fases["livre"] == 0


def test_alerta_80_20(resumos, cfg):
    from dgendurance.analise import gerar_alertas

    _, r = resumos["perfeita"]
    r.distribuicao_fc = {"z1_z2": 0.6, "z3": 0.3, "z4_mais": 0.1}
    assert any("80/20" in a.texto for a in gerar_alertas(r, cfg.alertas))


def test_importar_planilhas(tmp_path):
    from pathlib import Path
    from dgendurance.importar import importar

    raiz = Path(__file__).resolve().parent.parent / "config"
    atletas, erros = importar(raiz / "atletas_modelo.csv")
    assert not [e for e in erros if "(aviso)" not in e]
    bruno = next(a for a in atletas if a["nome"] == "Bruno Lima")
    assert bruno["nivel"] == "avancado" and bruno["volume"] == 1.2 and bruno["whatsapp"] == "5511999990002"
    carla = next(a for a in atletas if a["nome"] == "Carla Mendes")
    assert carla["dias_folga"] == ["seg", "qua"] and carla["prova_alvo"]["distancia"] == "olimpico"
    assert carla["ciclo"] == "2:1" and carla["prova_alvo"]["data"] == "2027-03-07"
    atletas, _ = importar(raiz / "atletas_modelo.xlsx")
    assert atletas[0]["intervals_id"] == "i000001"

    ruim = tmp_path / "ruim.csv"
    ruim.write_text("nome;nivel;folga;data prova\nZé;profissional;;\nJoão;iniciante;sabado;\n"
                    "Rui;avancado;feriado;\nLia;avancado;;30/02/2027\n", encoding="utf-8")
    atletas, erros = importar(ruim)
    graves = [e for e in erros if "(aviso)" not in e]
    assert [a["nome"] for a in atletas] == ["João"] and len(graves) == 3


# ---------------- vários treinadores (piloto) ----------------
@pytest.fixture
def treinador_teste():
    import shutil
    from dgendurance.config import PASTA_TREINADORES
    from dgendurance.treinadores import criar_treinador

    pasta = PASTA_TREINADORES / "pytest-treinador"
    shutil.rmtree(pasta, ignore_errors=True)
    criar_treinador("Pytest Treinador", "Equipe Pytest", slug="pytest-treinador")
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


def test_treinador_herda_e_sobrescreve(treinador_teste):
    from dgendurance.config import listar_treinadores

    assert "pytest-treinador" in listar_treinadores()
    (treinador_teste / "config.yaml").write_text(
        'treinador: {nome: "P", equipe: "Equipe Pytest"}\nalertas: {tsb_vermelho: -40}\n', encoding="utf-8")
    cfg = carregar_config(treinador="pytest-treinador")
    assert cfg.geral["treinador"]["equipe"] == "Equipe Pytest"
    assert cfg.alertas["tsb_vermelho"] == -40          # sobrescrito
    assert cfg.alertas["tsb_amarelo"] == -20           # herdado
    assert "Exemplos de mensagens do treinador" in cfg.estilo_feedback  # estilo próprio, não o do dono
    assert cfg.atletas == []


def test_chaves_nao_se_misturam(treinador_teste, monkeypatch):
    monkeypatch.setenv("INTERVALS_API_KEY", "chave-do-dono")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ia-do-dono")
    cfg = carregar_config(treinador="pytest-treinador")
    assert cfg.segredo("INTERVALS_API_KEY") == ""            # nunca usa a chave do dono
    assert cfg.segredo("ANTHROPIC_API_KEY") == "ia-do-dono"  # IA pode ser compartilhada no piloto
    (treinador_teste / "segredos.env").write_text("INTERVALS_API_KEY=chave-dele\nANTHROPIC_API_KEY=ia-dele\n")
    cfg = carregar_config(treinador="pytest-treinador")
    assert cfg.segredo("INTERVALS_API_KEY") == "chave-dele" and cfg.segredo("ANTHROPIC_API_KEY") == "ia-dele"
    assert carregar_config().segredo("INTERVALS_API_KEY") == "chave-do-dono"


def test_biblioteca_propria(treinador_teste):
    import yaml

    (treinador_teste / "biblioteca").mkdir()
    treinos = {"treinos": {"so_corrida": {"esporte": "Run", "nome": "Corrida do P", "tipo": "leve",
                                          "blocos": [{"titulo": "Principal", "passos": ["30m Z2 HR"]}]}}}
    semanas = {"semanas": {f: {"ter": ["so_corrida"]} for f in
                           ("base", "construcao", "pico", "polimento", "recuperacao")}}
    (treinador_teste / "biblioteca" / "treinos.yaml").write_text(yaml.safe_dump(treinos), encoding="utf-8")
    (treinador_teste / "biblioteca" / "semanas.yaml").write_text(yaml.safe_dump(semanas), encoding="utf-8")
    cfg = carregar_config(treinador="pytest-treinador")
    atleta = ATLETAS_DEMO[0][0]
    treinos_semana, _, _ = montar_semana(atleta, date(2026, 11, 30), cfg)
    assert [t.nome for t in treinos_semana] == ["Corrida do P"]


def test_demo_com_marca_do_treinador(treinador_teste, tmp_path):
    main(["semana", "--demo", "--sem-ia", "--treinador", "pytest-treinador",
          "--data", "2026-11-17", "--saida", str(tmp_path)])
    html = (tmp_path / "pytest-treinador" / "demo-2026-11-09" / "painel.html").read_text(encoding="utf-8")
    assert "Equipe Pytest" in html


def test_treinador_inexistente():
    with pytest.raises(ValueError, match="não encontrado"):
        carregar_config(treinador="nao-existe")
