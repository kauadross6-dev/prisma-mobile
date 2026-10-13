import os
import json
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODELO = "openai/gpt-oss-20b"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
cliente = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

PASTA = "dados"
os.makedirs(PASTA, exist_ok=True)

def sid():
    if "sid" not in session:
        session["sid"] = secrets.token_hex(8)
    return session["sid"]

def carregar(padrao):
    caminho = os.path.join(PASTA, f"memoria_{sid()}.json")
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return padrao
    return padrao

def salvar(dados):
    caminho = os.path.join(PASTA, f"memoria_{sid()}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

PADRAO = {"nome": None, "gostos": [], "historico": [], "personalidade": "padrao"}

PERSONALIDADES = {
    "padrao": "Você é Prisma, amigável. Responda em português, curto (máx 3 frases). NUNCA escreva raciocínio interno.",
    "bobao": "Você é Prisma, brincalhão. Responda em português, curto e engraçado, com gírias e emojis. Máx 3 frases.",
    "serio": "Você é Prisma, formal. Responda em português, direto e profissional, sem emojis. Máx 3 frases.",
    "curioso": "Você é Prisma, curioso. Responda em português, curto, terminando com pergunta. Máx 3 frases.",
}

SYSTEM_QUIZ = """Você cria quizzes. Responda APENAS com JSON:
{"explicacao": "Curta (máx 4 frases).", "perguntas": [{"p":"?","opcoes":["A","B","C","D"],"certa":0,"explica":"."}]}
Sempre 4 opções. "certa" é índice 0-3. Gere exatamente a quantidade pedida."""

SYSTEM_HUMOR = "Analise o histórico de humor e escreva um resumo acolhedor (máx 4 frases), com incentivo. Sem marcadores técnicos."

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    if not cliente:
        return jsonify({"resposta": "⚠️ Chave da IA não configurada."})
    msg = request.get_json().get("mensagem", "").strip()
    if not msg:
        return jsonify({"resposta": "Digite algo!"})

    m = carregar(PADRAO)
    prompt = PERSONALIDADES.get(m["personalidade"], PERSONALIDADES["padrao"])
    if m["nome"]:
        prompt += f"\nO usuário se chama {m['nome']}."
    if m["gostos"]:
        prompt += f"\nEle gosta de: {', '.join(m['gostos'])}."

    mensagens = [{"role": "system", "content": prompt}]
    for h in m["historico"][-6:]:
        mensagens.append(h)
    mensagens.append({"role": "user", "content": msg})

    try:
        r = cliente.chat.completions.create(model=MODELO, messages=mensagens,
                                             temperature=0.7, max_tokens=400)
        texto = r.choices[0].message.content.strip()
        m["historico"].append({"role": "user", "content": msg})
        m["historico"].append({"role": "assistant", "content": texto})
        if len(m["historico"]) > 20:
            m["historico"] = m["historico"][-20:]
        salvar(m)
        return jsonify({"resposta": texto})
    except Exception as e:
        return jsonify({"resposta": f"❌ Erro: {str(e)[:150]}"})

@app.route("/api/memoria", methods=["GET"])
def get_memoria():
    m = carregar(PADRAO)
    return jsonify({"nome": m["nome"] or "", "gostos": ", ".join(m["gostos"]),
                    "personalidade": m["personalidade"]})

@app.route("/api/memoria", methods=["POST"])
def set_memoria():
    d = request.get_json()
    m = carregar(PADRAO)
    if d.get("nome") is not None:
        m["nome"] = d["nome"].strip() or None
    if d.get("gostos") is not None:
        m["gostos"] = [g.strip() for g in d["gostos"].split(",") if g.strip()]
    if d.get("personalidade"):
        m["personalidade"] = d["personalidade"]
    if d.get("limpar"):
        m["historico"] = []
    salvar(m)
    return jsonify({"ok": True})

@app.route("/api/quiz/gerar", methods=["POST"])
def gerar_quiz():
    if not cliente:
        return jsonify({"erro": "Chave não configurada."})
    d = request.get_json()
    tema = d.get("tema", "").strip()
    dif = d.get("dificuldade", "facil")
    num = max(1, min(20, int(d.get("numero", 3))))
    if not tema:
        return jsonify({"erro": "Digite um tema."})
    try:
        r = cliente.chat.completions.create(
            model=MODELO,
            messages=[{"role": "system", "content": SYSTEM_QUIZ},
                      {"role": "user", "content": f"Tema: {tema}\nDificuldade: {dif}\nPerguntas: {num}"}],
            temperature=0.7, max_tokens=250*num+500,
            response_format={"type": "json_object"})
        dados = json.loads(r.choices[0].message.content.strip())
        dados.setdefault("explicacao", "")
        dados.setdefault("perguntas", [])
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": f"Erro: {str(e)[:150]}", "explicacao": "", "perguntas": []})

@app.route("/api/humor", methods=["POST"])
def humor_reg():
    d = request.get_json()
    nota = d.get("nota")
    if nota is None:
        return jsonify({"erro": "Nota não fornecida"})
    m = carregar(PADRAO)
    m.setdefault("humor", []).append({
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nota": nota, "motivo": d.get("motivo", "").strip()})
    salvar(m)
    if nota <= 3: frase = "Respira fundo. Você já superou coisas maiores. 💙"
    elif nota <= 7: frase = "Dia médio também é dia. Segue em frente. 🌤️"
    else: frase = "Que bom te ver bem! Aproveita esse dia. ☀️"
    return jsonify({"frase": frase, "nota": nota})

@app.route("/api/humor/historico", methods=["GET"])
def humor_hist():
    m = carregar(PADRAO)
    regs = m.get("humor", [])[-10:]
    regs.reverse()
    return jsonify({"registros": regs})

@app.route("/api/humor/analise", methods=["POST"])
def humor_analise():
    if not cliente:
        return jsonify({"analise": "Chave não configurada."})
    m = carregar(PADRAO)
    regs = m.get("humor", [])
    if not regs:
        return jsonify({"analise": "Ainda não tenho registros."})
    txt = "\n".join([f"{r['data']} - Nota: {r['nota']}" + (f" - {r['motivo']}" if r.get('motivo') else "")
                     for r in regs[-10:]])
    try:
        r = cliente.chat.completions.create(
            model=MODELO,
            messages=[{"role": "system", "content": SYSTEM_HUMOR},
                      {"role": "user", "content": f"Histórico:\n{txt}"}],
            temperature=0.7, max_tokens=300)
        return jsonify({"analise": r.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({"analise": f"❌ Erro: {str(e)[:150]}"})

@app.route("/api/mural", methods=["POST"])
def mural_salvar():
    t = request.get_json().get("texto", "").strip()
    if not t:
        return jsonify({"erro": "Escreva algo"})
    m = carregar(PADRAO)
    m.setdefault("mural", []).append({
        "texto": t, "data": datetime.now().strftime("%d/%m/%Y %H:%M")})
    salvar(m)
    return jsonify({"ok": True})

@app.route("/api/mural", methods=["GET"])
def mural_listar():
    m = carregar(PADRAO)
    return jsonify({"itens": m.get("mural", [])[-10:]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
