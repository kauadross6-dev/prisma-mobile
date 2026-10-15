import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODELO = "openai/gpt-oss-20b"

app = Flask(__name__)
cliente = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

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

    d = request.get_json()
    msg = d.get("mensagem", "").strip()
    if not msg:
        return jsonify({"resposta": "Digite algo!"})

    # Memória vem do cliente (localStorage)
    nome = d.get("nome") or "amigo"
    gostos = d.get("gostos") or ""
    personalidade = d.get("personalidade", "padrao")
    historico = d.get("historico", [])

    prompt = PERSONALIDADES.get(personalidade, PERSONALIDADES["padrao"])
    prompt += f"\nO usuário se chama {nome}."
    if gostos:
        prompt += f"\nEle gosta de: {gostos}."

    mensagens = [{"role": "system", "content": prompt}]
    for h in historico[-6:]:
        if isinstance(h, dict) and "role" in h and "content" in h:
            mensagens.append(h)
    mensagens.append({"role": "user", "content": msg})

    try:
        r = cliente.chat.completions.create(
            model=MODELO, messages=mensagens,
            temperature=0.7, max_tokens=400,
        )
        texto = r.choices[0].message.content.strip()
        return jsonify({"resposta": texto})
    except Exception as e:
        return jsonify({"resposta": f"❌ Erro: {str(e)[:150]}"})


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
            temperature=0.7, max_tokens=250 * num + 500,
            response_format={"type": "json_object"})
        dados = json.loads(r.choices[0].message.content.strip())
        dados.setdefault("explicacao", "")
        dados.setdefault("perguntas", [])
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": f"Erro: {str(e)[:150]}", "explicacao": "", "perguntas": []})


@app.route("/api/humor/analise", methods=["POST"])
def humor_analise():
    if not cliente:
        return jsonify({"analise": "Chave não configurada."})
    d = request.get_json()
    regs = d.get("registros", [])
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
