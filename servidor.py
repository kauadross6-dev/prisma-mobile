"""
PRISMA MOBILE — Servidor Flask
Chat + Quiz dinâmico (com IA) + Bem-Estar + Mural
"""

import os
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from groq import Groq

# A chave agora vem do ambiente (Render) ou do padrão local se não existir
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "gsk_SuaChaveAquiSeQuiserTestarLocal")
MODELO = "openai/gpt-oss-20b"

app = Flask(__name__)

# Só cria o cliente se a chave existir
cliente = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

MEMORIA = {"nome": None, "gostos": [], "humor_hoje": None, "mural": []}

SYSTEM_PROMPT = """
Você é Prisma, um assistente de IA amigável, criado pelo Kauã, um aluno do ensino médio.
Fale sempre em português do Brasil, de forma curta e clara (máximo 3 frases).
Você ajuda com estudos, dúvidas, quiz, bem-estar e conversa.
Se alguém estiver triste ou ansioso, responda com empatia.
NUNCA use marcadores como "Thinking Process", "Initial Idea", "Constraint".
Apenas responda direto ao usuário.
"""

SYSTEM_PROMPT_QUIZ = """
Você é um professor que cria quizzes educativos em português do Brasil.

O aluno vai te dizer um tema, a dificuldade e quantas perguntas quer.

NÍVEIS DE DIFICULDADE:
- facil: perguntas diretas, respostas claras, para quem está começando
- medio: perguntas que exigem um pouco de raciocínio
- dificil: perguntas que exigem análise, comparação e aplicação de conceitos

Você deve responder APENAS com um JSON válido, sem texto antes ou depois, neste formato exato:

{
  "explicacao": "Uma explicação curta e simples do tema, em no máximo 4 frases, linguagem para aluno do ensino médio.",
  "perguntas": [
    {
      "p": "Texto da pergunta?",
      "opcoes": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "certa": 0,
      "explica": "Por que essa é a resposta certa, em uma frase."
    }
  ]
}

REGRAS IMPORTANTES:
- "certa" é o índice da opção correta (0, 1, 2 ou 3).
- SEMPRE 4 opções por pergunta.
- Gere EXATAMENTE a quantidade de perguntas que o aluno pedir.
- Nada de markdown, nada de comentários, apenas o JSON puro.
"""


@app.route("/")
def home():
    return render_template("index.html")


# =====================
# CHAT
# =====================
@app.route("/api/chat", methods=["POST"])
def chat():
    if not cliente:
        return jsonify({"resposta": "⚠️ Chave da IA não configurada."})

    dados = request.get_json()
    mensagem = dados.get("mensagem", "").strip()
    if not mensagem:
        return jsonify({"resposta": "Digite algo pra eu responder!"})

    try:
        resposta = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": mensagem},
            ],
            temperature=0.7,
            max_tokens=400,
        )
        texto = resposta.choices[0].message.content.strip()
        return jsonify({"resposta": texto})
    except Exception as e:
        return jsonify({"resposta": f"❌ Erro: {str(e)[:150]}"})


# =====================
# QUIZ DINÂMICO
# =====================
@app.route("/api/quiz/gerar", methods=["POST"])
def gerar_quiz():
    if not cliente:
        return jsonify({"erro": "⚠️ Chave da IA não configurada."})

    dados = request.get_json()
    tema = dados.get("tema", "").strip()
    dificuldade = dados.get("dificuldade", "facil")
    numero = int(dados.get("numero", 3))

    if not tema:
        return jsonify({"erro": "Digite um tema pra estudar."})

    if dificuldade not in ["facil", "medio", "dificil"]:
        dificuldade = "facil"

    numero = max(1, min(20, numero))

    try:
        resposta = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_QUIZ},
                {"role": "user", "content": f"Tema: {tema}\nDificuldade: {dificuldade}\nNúmero de perguntas: {numero}"},
            ],
            temperature=0.7,
            max_tokens=250 * numero + 500,
            response_format={"type": "json_object"},
        )
        texto = resposta.choices[0].message.content.strip()
        dados_quiz = json.loads(texto)

        if "explicacao" not in dados_quiz:
            dados_quiz["explicacao"] = "Não consegui gerar explicação."
        if "perguntas" not in dados_quiz:
            dados_quiz["perguntas"] = []

        return jsonify(dados_quiz)

    except json.JSONDecodeError:
        return jsonify({
            "erro": "A IA não conseguiu gerar o quiz. Tente novamente.",
            "explicacao": "",
            "perguntas": [],
        })
    except Exception as e:
        return jsonify({
            "erro": f"Erro: {str(e)[:150]}",
            "explicacao": "",
            "perguntas": [],
        })


# =====================
# HUMOR
# =====================
@app.route("/api/humor", methods=["POST"])
def humor():
    dados = request.get_json()
    nota = dados.get("nota")
    MEMORIA["humor_hoje"] = {"nota": nota, "data": datetime.now().strftime("%d/%m/%Y")}
    if nota <= 3:
        frase = "Respira fundo. Você já superou coisas maiores. 💙"
    elif nota <= 7:
        frase = "Dia médio também é dia. Segue em frente. 🌤️"
    else:
        frase = "Que bom te ver bem! Aproveita esse dia. ☀️"
    return jsonify({"frase": frase, "nota": nota})


# =====================
# MURAL
# =====================
@app.route("/api/mural", methods=["POST"])
def mural():
    dados = request.get_json()
    texto = dados.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "Escreva algo"})
    MEMORIA["mural"].append({
        "texto": texto,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    return jsonify({"ok": True, "total": len(MEMORIA["mural"])})


@app.route("/api/mural", methods=["GET"])
def listar_mural():
    return jsonify({"itens": MEMORIA["mural"][-10:]})


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta, debug=False)