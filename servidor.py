"""
PRISMA MOBILE — Servidor Flask
Chat + Quiz + Mural + Humor (com banco de dados na nuvem)
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from groq import Groq
from supabase import create_client, Client

# =====================
# CONFIGURAÇÕES E CHAVES
# =====================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
MODELO = "openai/gpt-oss-20b"

app = Flask(__name__)
cliente_groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# =====================
# PROMPTS
# =====================
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
Você deve responder APENAS com um JSON válido, neste formato:
{
  "explicacao": "Explicação curta e simples do tema, em no máximo 4 frases.",
  "perguntas": [
    {
      "p": "Texto da pergunta?",
      "opcoes": ["Opção A", "Opção B", "Opção C", "Opção D"],
      "certa": 0,
      "explica": "Por que essa é a resposta certa."
    }
  ]
}
REGRAS: "certa" é o índice (0 a 3). SEMPRE 4 opções. Gere EXATAMENTE a quantidade pedida. Apenas o JSON puro.
"""

SYSTEM_PROMPT_HUMOR = """
Você é um assistente empático que analisa o histórico de humor de uma pessoa.
Você receberá uma lista de registros com data, nota (1 a 10) e, às vezes, um motivo.
Sua tarefa é escrever um resumo acolhedor, em português do Brasil, destacando como a pessoa começou e como está agora, padrões de melhora ou piora, e uma mensagem de incentivo.
Seja breve (máximo 4 frases), gentil e personalize com base nos motivos fornecidos.
NUNCA use marcadores técnicos. Apenas responda com o texto final.
"""

@app.route("/")
def home():
    return render_template("index.html")

# =====================
# CHAT
# =====================
@app.route("/api/chat", methods=["POST"])
def chat():
    if not cliente_groq:
        return jsonify({"resposta": "⚠️ Chave da IA não configurada no servidor."})

    dados = request.get_json()
    mensagem = dados.get("mensagem", "").strip()
    if not mensagem:
        return jsonify({"resposta": "Digite algo pra eu responder!"})

    try:
        resposta = cliente_groq.chat.completions.create(
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
    if not cliente_groq:
        return jsonify({"erro": "⚠️ Chave da IA não configurada no servidor."})

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
        resposta = cliente_groq.chat.completions.create(
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
        if "explicacao" not in dados_quiz: dados_quiz["explicacao"] = "Não consegui gerar explicação."
        if "perguntas" not in dados_quiz: dados_quiz["perguntas"] = []
        return jsonify(dados_quiz)
    except Exception as e:
        return jsonify({"erro": f"Erro: {str(e)[:150]}", "explicacao": "", "perguntas": []})

# =====================
# MURAL (COM BANCO DE DADOS)
# =====================
@app.route("/api/mural", methods=["POST"])
def mural_salvar():
    if not supabase: return jsonify({"erro": "Banco de dados não configurado."})
    dados = request.get_json()
    texto = dados.get("texto", "").strip()
    if not texto: return jsonify({"erro": "Escreva algo"})

    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        supabase.table("mural").insert({"texto": texto, "data": data_str}).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)[:100]})

@app.route("/api/mural", methods=["GET"])
def mural_listar():
    if not supabase: return jsonify({"itens": []})
    try:
        resposta = supabase.table("mural").select("*").order("id", desc=True).limit(10).execute()
        return jsonify({"itens": resposta.data})
    except Exception as e:
        return jsonify({"itens": []})

# =====================
# HUMOR (COM BANCO DE DADOS E ANÁLISE)
# =====================
@app.route("/api/humor", methods=["POST"])
def registrar_humor():
    if not supabase: return jsonify({"erro": "Banco de dados não configurado."})
    dados = request.get_json()
    nota = dados.get("nota")
    motivo = dados.get("motivo", "").strip()
    if nota is None: return jsonify({"erro": "Nota não fornecida"})

    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        supabase.table("humor").insert({"nota": nota, "motivo": motivo, "data": data_str}).execute()
        
        if nota <= 3: frase = "Respira fundo. Você já superou coisas maiores. 💙"
        elif nota <= 7: frase = "Dia médio também é dia. Segue em frente. 🌤️"
        else: frase = "Que bom te ver bem! Aproveita esse dia. ☀️"
        
        return jsonify({"frase": frase, "nota": nota})
    except Exception as e:
        return jsonify({"erro": str(e)[:100]})

@app.route("/api/humor/historico", methods=["GET"])
def historico_humor():
    if not supabase: return jsonify({"registros": []})
    try:
        resposta = supabase.table("humor").select("*").order("id", desc=True).limit(10).execute()
        return jsonify({"registros": resposta.data})
    except Exception as e:
        return jsonify({"registros": []})

@app.route("/api/humor/analise", methods=["POST"])
def analisar_humor():
    if not cliente_groq or not supabase: return jsonify({"erro": "Serviço não configurado."})
    try:
        resposta_db = supabase.table("humor").select("*").order("id", desc=True).limit(10).execute()
        registros = resposta_db.data
        if not registros:
            return jsonify({"analise": "Ainda não tenho registros suficientes para analisar."})

        texto_historico = "\n".join([f"{r['data']} - Nota: {r['nota']}" + (f" - Motivo: {r['motivo']}" if r.get('motivo') else "") for r in registros])
        resposta = cliente_groq.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_HUMOR},
                {"role": "user", "content": f"Aqui está o histórico:\n{texto_historico}"},
            ],
            temperature=0.7, max_tokens=300,
        )
        return jsonify({"analise": resposta.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({"analise": f"❌ Erro: {str(e)[:150]}"})

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta, debug=False)