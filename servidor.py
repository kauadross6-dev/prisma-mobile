import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODELO = "openai/gpt-oss-20b"

app = Flask(__name__)
cliente = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

PASTA = "dados"
os.makedirs(PASTA, exist_ok=True)

def carregar(nome, padrao):
    caminho = os.path.join(PASTA, nome)
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return padrao
    return padrao

def salvar(nome, dados):
    caminho = os.path.join(PASTA, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# =====================
# PERSONALIDADES
# =====================
PERSONALIDADES = {
    "padrao": (
        "Você é Prisma, um assistente de IA amigável, criado pelo Kauã. "
        "Responda em português do Brasil, de forma curta e clara (máx 3 frases). "
        "NUNCA escreva seu raciocínio interno, apenas a resposta final."
    ),
    "bobao": (
        "Você é Prisma, um assistente MUITO brincalhão, criado pelo Kauã. "
        "Responda em português do Brasil, de forma curta e engraçada, com gírias leves e emojis. "
        "Máx 3 frases. NUNCA escreva seu raciocínio interno."
    ),
    "serio": (
        "Você é Prisma, um assistente formal e objetivo, criado pelo Kauã. "
        "Responda em português do Brasil, direto e profissional, sem emojis. "
        "Máx 3 frases. NUNCA escreva seu raciocínio interno."
    ),
    "curioso": (
        "Você é Prisma, um assistente curioso e instigante, criado pelo Kauã. "
        "Responda em português do Brasil, de forma curta, sempre terminando com uma pergunta curiosa. "
        "Máx 3 frases. NUNCA escreva seu raciocínio interno."
    ),
}

SYSTEM_QUIZ = """
Você é um professor que cria quizzes. O aluno diz tema, dificuldade e número de perguntas.
Responda APENAS com JSON válido:
{
  "explicacao": "Explicação curta do tema (máx 4 frases).",
  "perguntas": [
    {"p": "Pergunta?", "opcoes": ["A","B","C","D"], "certa": 0, "explica": "Por quê."}
  ]
}
REGRAS: "certa" é índice 0-3. Sempre 4 opções. Gere exatamente a quantidade pedida. Só JSON puro.
"""

SYSTEM_HUMOR = """
Você analisa um histórico de humor com data, nota (1-10) e motivo.
Escreva um resumo acolhedor em português (máx 4 frases), destacando evolução e uma mensagem de incentivo.
NUNCA use marcadores técnicos.
"""

# =====================
# CHAT COM MEMÓRIA
# =====================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    if not cliente:
        return jsonify({"resposta": "⚠️ Chave da IA não configurada."})
    dados = request.get_json()
    msg = dados.get("mensagem", "").strip()
    if not msg:
        return jsonify({"resposta": "Digite algo!"})

    memoria = carregar("memoria.json", {
        "nome": None, "gostos": [], "historico": [], "personalidade": "padrao"
    })

    prompt = PERSONALIDADES.get(memoria["personalidade"], PERSONALIDADES["padrao"])
    if memoria["nome"]:
        prompt += f"\nO usuário se chama {memoria['nome']}."
    if memoria["gostos"]:
        prompt += f"\nEle gosta de: {', '.join(memoria['gostos'])}."

    mensagens = [{"role": "system", "content": prompt}]
    for m in memoria["historico"][-6:]:
        mensagens.append(m)
    mensagens.append({"role": "user", "content": msg})

    try:
        r = cliente.chat.completions.create(
            model=MODELO, messages=mensagens,
            temperature=0.7, max_tokens=400,
        )
        texto = r.choices[0].message.content.strip()
        memoria["historico"].append({"role": "user", "content": msg})
        memoria["historico"].append({"role": "assistant", "content": texto})
        if len(memoria["historico"]) > 20:
            memoria["historico"] = memoria["historico"][-20:]
        salvar("memoria.json", memoria)
        return jsonify({"resposta": texto})
    except Exception as e:
        return jsonify({"resposta": f"❌ Erro: {str(e)[:150]}"})

# =====================
# MEMÓRIA
# =====================
@app.route("/api/memoria", methods=["GET"])
def get_memoria():
    m = carregar("memoria.json", {
        "nome": None, "gostos": [], "historico": [], "personalidade": "padrao"
    })
    return jsonify({
        "nome": m["nome"] or "",
        "gostos": ", ".join(m["gostos"]),
        "personalidade": m["personalidade"],
        "historico": m["historico"][-6:],
    })

@app.route("/api/memoria", methods=["POST"])
def set_memoria():
    dados = request.get_json()
    m = carregar("memoria.json", {
        "nome": None, "gostos": [], "historico": [], "personalidade": "padrao"
    })
    if dados.get("nome") is not None:
        m["nome"] = dados["nome"].strip() or None
    if dados.get("gostos") is not None:
        m["gostos"] = [g.strip() for g in dados["gostos"].split(",") if g.strip()]
    if dados.get("personalidade"):
        m["personalidade"] = dados["personalidade"]
    if dados.get("limpar"):
        m["historico"] = []
    salvar("memoria.json", m)
    return jsonify({"ok": True})

# =====================
# QUIZ
# =====================
@app.route("/api/quiz/gerar", methods=["POST"])
def gerar_quiz():
    if not cliente:
        return jsonify({"erro": "Chave da IA não configurada."})
    d = request.get_json()
    tema = d.get("tema", "").strip()
    dif = d.get("dificuldade", "facil")
    num = max(1, min(20, int(d.get("numero", 3))))
    if not tema:
        return jsonify({"erro": "Digite um tema."})
    if dif not in ["facil", "medio", "dificil"]:
        dif = "facil"
    try:
        r = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SYSTEM_QUIZ},
                {"role": "user", "content": f"Tema: {tema}\nDificuldade: {dif}\nPerguntas: {num}"},
            ],
            temperature=0.7, max_tokens=250 * num + 500,
            response_format={"type": "json_object"},
        )
        texto = r.choices[0].message.content.strip()
        dados = json.loads(texto)
        dados.setdefault("explicacao", "")
        dados.setdefault("perguntas", [])
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": f"Erro: {str(e)[:150]}", "explicacao": "", "perguntas": []})

# =====================
# HUMOR
# =====================
@app.route("/api/humor", methods=["POST"])
def humor_registrar():
    d = request.get_json()
    nota = d.get("nota")
    motivo = d.get("motivo", "").strip()
    if nota is None:
        return jsonify({"erro": "Nota não fornecida"})
    registros = carregar("humor.json", [])
    registros.append({
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nota": nota, "motivo": motivo,
    })
    salvar("humor.json", registros)

    if nota <= 3: frase = "Respira fundo. Você já superou coisas maiores. 💙"
    elif nota <= 7: frase = "Dia médio também é dia. Segue em frente. 🌤️"
    else: frase = "Que bom te ver bem! Aproveita esse dia. ☀️"
    return jsonify({"frase": frase, "nota": nota})

@app.route("/api/humor/historico", methods=["GET"])
def humor_hist():
    registros = carregar("humor.json", [])
    ultimos = registros[-10:]
    ultimos.reverse()
    return jsonify({"registros": ultimos})

@app.route("/api/humor/analise", methods=["POST"])
def humor_analise():
    if not cliente:
        return jsonify({"analise": "Chave não configurada."})
    registros = carregar("humor.json", [])
    if not registros:
        return jsonify({"analise": "Ainda não tenho registros."})
    ultimos = registros[-10:]
    texto = "\n".join([
        f"{r['data']} - Nota: {r['nota']}" + (f" - {r['motivo']}" if r.get('motivo') else "")
        for r in ultimos
    ])
    try:
        r = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SYSTEM_HUMOR},
                {"role": "user", "content": f"Histórico:\n{texto}"},
            ],
            temperature=0.7, max_tokens=300,
        )
        return jsonify({"analise": r.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({"analise": f"❌ Erro: {str(e)[:150]}"})

# =====================
# MURAL
# =====================
@app.route("/api/mural", methods=["POST"])
def mural_salvar():
    d = request.get_json()
    texto = d.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "Escreva algo"})
    itens = carregar("mural.json", [])
    itens.append({
        "texto": texto,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    salvar("mural.json", itens)
    return jsonify({"ok": True})

@app.route("/api/mural", methods=["GET"])
def mural_listar():
    itens = carregar("mural.json", [])
    return jsonify({"itens": itens[-10:]})

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta, debug=False)
