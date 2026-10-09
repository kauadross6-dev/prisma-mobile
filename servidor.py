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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
MODELO = "openai/gpt-oss-20b"

app = Flask(__name__)
cliente = Groq(api_key=GROQ_API_KEY)

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

O aluno vai te dizer um tema (ex: "frações", "Revolução Francesa", "fotossíntese").

Você deve responder APENAS com um JSON válido, sem texto antes ou depois, neste formato exato:

{
  "explicacao": "Uma explicação curta e simples do tema, em no máximo 4 frases, linguagem para aluno do ensino médio.",
  "perguntas": [
    {
      "p": "Texto da pergunta 1?",
      "opcoes": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "certa": 0,
      "explica": "Por que essa é a resposta certa, em uma frase."
    },
    {
      "p": "Texto da pergunta 2?",
      "opcoes": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "certa": 2,
      "explica": "Por que essa é a resposta certa."
    },
    {
      "p": "Texto da pergunta 3?",
      "opcoes": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "certa": 1,
      "explica": "Por que essa é a resposta certa."
    }
  ]
}

REGRAS IMPORTANTES:
- "certa" é o índice da opção correta (0, 1, 2 ou 3).
- SEMPRE 4 opções por pergunta.
- SEMPRE 3 perguntas.
- Nada de markdown, nada de comentários, apenas o JSON puro.
- Se o tema não existir ou for inadequado, retorne:
  {"explicacao": "Não entendi o tema. Tente algo como 'frações' ou 'fotossíntese'.", "perguntas": []}
"""


@app.route("/")
def home():
    return render_template("index.html")


# =====================
# CHAT
# =====================
@app.route("/api/chat", methods=["POST"])
def chat():
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
    dados = request.get_json()
    tema = dados.get("tema", "").strip()
    if not tema:
        return jsonify({"erro": "Digite um tema pra estudar."})

    try:
        resposta = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_QUIZ},
                {"role": "user", "content": f"Tema: {tema}"},
            ],
            temperature=0.7,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        texto = resposta.choices[0].message.content.strip()

        # Parse do JSON
        dados_quiz = json.loads(texto)

        # Validação básica
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
