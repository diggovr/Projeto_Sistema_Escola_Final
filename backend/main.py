# ════════════════════════════════════════════════════════
#  RS Treinamento & Consultoria — Sistema Escolar
#  backend/main.py  |  API REST com FastAPI + SQLite
#
#  COMO RODAR:
#    1. pip install fastapi uvicorn httpx python-dotenv
#    2. Copie .env.example para .env e coloque sua API Key
#    3. python main.py
#    4. Acesse:  http://localhost:8000
#    5. Docs:    http://localhost:8000/docs
# ════════════════════════════════════════════════════════

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os
import httpx                      # cliente HTTP assíncrono
from dotenv import load_dotenv    # lê o arquivo .env

# ── Carrega variáveis de ambiente do arquivo .env ─────
# A API Key do Claude fica em backend/.env — NUNCA no código
# O arquivo .env NÃO deve ser commitado no GitHub (.gitignore)
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')

# ── Caminho do banco de dados ──────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), 'escola.db')

# ── Criação do app FastAPI ─────────────────────────────
app = FastAPI(
    title="RS Sistema Escolar",
    description="API REST para o Sistema Escolar — ADS Mobile Development",
    version="1.0.0"
)

# ── CORS: permite o frontend acessar a API ─────────────
# Em produção, substitua "*" pelo domínio real do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════════════
#  BANCO DE DADOS — Inicialização das tabelas
# ════════════════════════════════════════════════════════

def get_db():
    """Retorna conexão com o banco SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # resultados como dicionário
    return conn


def init_db():
    """Cria as tabelas se não existirem."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nome    TEXT    NOT NULL,
            email   TEXT    NOT NULL UNIQUE,
            senha   TEXT    NOT NULL,
            perfil  TEXT    DEFAULT 'aluno'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cursos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nome          TEXT    NOT NULL,
            descricao     TEXT,
            carga_horaria INTEGER,
            modalidade    TEXT    DEFAULT 'Presencial'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alunos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nome      TEXT    NOT NULL,
            email     TEXT    NOT NULL UNIQUE,
            cpf       TEXT,
            data_nasc TEXT,
            telefone  TEXT,
            curso_id  INTEGER REFERENCES cursos(id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado:", DB_PATH)


init_db()

# ════════════════════════════════════════════════════════
#  MODELOS  (Pydantic — validação automática dos dados)
# ════════════════════════════════════════════════════════

class UsuarioIn(BaseModel):
    nome:   str
    email:  str
    senha:  str
    perfil: Optional[str] = "aluno"

class LoginIn(BaseModel):
    email: str
    senha: str

class CursoIn(BaseModel):
    nome:          str
    descricao:     Optional[str] = None
    carga_horaria: Optional[int] = None
    modalidade:    Optional[str] = "Presencial"

class AlunoIn(BaseModel):
    nome:      str
    email:     str
    cpf:       Optional[str] = None
    data_nasc: Optional[str] = None
    telefone:  Optional[str] = None
    curso_id:  Optional[int] = None

# ════════════════════════════════════════════════════════
#  ROTAS  — Health check
# ════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "online", "sistema": "RS Sistema Escolar"}

# ════════════════════════════════════════════════════════
#  ROTAS  — Usuários
# ════════════════════════════════════════════════════════

@app.get("/usuarios")
def listar_usuarios():
    conn = get_db()
    rows = conn.execute("SELECT id, nome, email, perfil FROM usuarios").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/usuarios", status_code=201)
def criar_usuario(dados: UsuarioIn):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)",
            (dados.nome, dados.email, dados.senha, dados.perfil)
        )
        conn.commit()
        novo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
    conn.close()
    return {"id": novo_id, "nome": dados.nome, "email": dados.email, "perfil": dados.perfil}


@app.delete("/usuarios/{id}")
def excluir_usuario(id: int):
    conn = get_db()
    conn.execute("DELETE FROM usuarios WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return {"mensagem": "Usuário excluído."}


@app.post("/login")
def login(dados: LoginIn):
    conn = get_db()
    row = conn.execute(
        "SELECT id, nome, email, perfil FROM usuarios WHERE email = ? AND senha = ?",
        (dados.email, dados.senha)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Email ou senha inválidos.")
    return dict(row)

# ════════════════════════════════════════════════════════
#  ROTAS  — Cursos
# ════════════════════════════════════════════════════════

@app.get("/cursos")
def listar_cursos():
    conn = get_db()
    rows = conn.execute("SELECT * FROM cursos").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/cursos", status_code=201)
def criar_curso(dados: CursoIn):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO cursos (nome, descricao, carga_horaria, modalidade) VALUES (?, ?, ?, ?)",
        (dados.nome, dados.descricao, dados.carga_horaria, dados.modalidade)
    )
    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()
    return {"id": novo_id, **dados.dict()}


@app.delete("/cursos/{id}")
def excluir_curso(id: int):
    conn = get_db()
    conn.execute("DELETE FROM cursos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return {"mensagem": "Curso excluído."}

# ════════════════════════════════════════════════════════
#  ROTAS  — Alunos
# ════════════════════════════════════════════════════════

@app.get("/alunos")
def listar_alunos():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id, a.nome, a.email, a.cpf, a.data_nasc, a.telefone,
               a.curso_id, c.nome AS curso_nome
        FROM alunos a
        LEFT JOIN cursos c ON a.curso_id = c.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/alunos", status_code=201)
def criar_aluno(dados: AlunoIn):
    conn = get_db()
    try:
        cursor = conn.execute(
            """INSERT INTO alunos (nome, email, cpf, data_nasc, telefone, curso_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dados.nome, dados.email, dados.cpf, dados.data_nasc, dados.telefone, dados.curso_id)
        )
        conn.commit()
        novo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="E-mail já cadastrado para outro aluno.")
    conn.close()
    return {"id": novo_id, **dados.dict()}


@app.delete("/alunos/{id}")
def excluir_aluno(id: int):
    conn = get_db()
    conn.execute("DELETE FROM alunos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return {"mensagem": "Aluno excluído."}


# ════════════════════════════════════════════════════════
#  ROTAS  — IA Generativa (Claude / Anthropic)
#
#  ARQUITETURA DE SEGURANÇA:
#
#  browser          backend (Python)        Claude API
#    │                    │                      │
#    │  GET /relatorio/   │                      │
#    │  narrativa         │                      │
#    │ ─────────────────▶ │                      │
#    │                    │  POST /v1/messages   │
#    │                    │  + API Key (oculta)  │
#    │                    │ ───────────────────▶ │
#    │                    │                      │
#    │                    │  { narrativa: "..." }│
#    │                    │ ◀─────────────────── │
#    │  { narrativa }     │                      │
#    │ ◀───────────────── │                      │
#
#  A chave NUNCA sai do servidor Python.
#  O browser só vê o texto gerado — nunca a key.
# ════════════════════════════════════════════════════════

@app.get("/relatorio/narrativa")
async def gerar_narrativa():
    """
    Coleta dados reais do banco, monta o prompt e chama o Claude.
    Retorna a narrativa gerada pela IA.
    A API Key fica no servidor — o browser nunca a vê.
    """

    # ── 1. Verifica se a API Key está configurada ──────
    if not CLAUDE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "CLAUDE_API_KEY não configurada. "
                "Edite o arquivo backend/.env e adicione: "
                "CLAUDE_API_KEY=sk-ant-..."
            )
        )

    # ── 2. Coleta dados do banco SQLite ────────────────
    conn = get_db()

    total_alunos   = conn.execute("SELECT COUNT(*) FROM alunos").fetchone()[0]
    total_cursos   = conn.execute("SELECT COUNT(*) FROM cursos").fetchone()[0]
    total_usuarios = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]

    # Distribuição: quantos alunos em cada curso
    dist_rows = conn.execute("""
        SELECT c.nome, c.modalidade, COUNT(a.id) AS total
        FROM cursos c
        LEFT JOIN alunos a ON a.curso_id = c.id
        GROUP BY c.id
        ORDER BY total DESC
    """).fetchall()
    conn.close()

    distribuicao = "\n".join(
        f"  - {r['nome']} ({r['modalidade']}): {r['total']} aluno(s)"
        for r in dist_rows
    ) or "  (Nenhum curso cadastrado ainda)"

    # ── 3. Monta o prompt com dados reais ──────────────
    prompt = f"""Você é um analista educacional da RS Treinamento & Consultoria.
Analise os dados do sistema escolar abaixo e escreva uma narrativa profissional em português.
Use no máximo 4 parágrafos curtos. Mencione destaques e, se relevante, pontos de atenção.

DADOS DO SISTEMA:
- Total de alunos matriculados: {total_alunos}
- Total de cursos disponíveis:  {total_cursos}
- Total de usuários no sistema: {total_usuarios}

DISTRIBUIÇÃO POR CURSO:
{distribuicao}

Escreva a narrativa agora:"""

    # ── 4. Chama a API do Claude (server-side) ─────────
    # httpx faz a requisição HTTP a partir do Python
    # O browser nunca vê a API Key — ela sai apenas deste servidor
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         CLAUDE_API_KEY,   # ← segura no .env
                "anthropic-version": "2023-06-01",
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Erro na API do Claude: {resp.text}"
        )

    # ── 5. Retorna narrativa + metadados para o frontend ─
    data = resp.json()
    narrativa = data["content"][0]["text"]

    return {
        "narrativa": narrativa,
        "modelo":    "claude-sonnet-4-20250514",
        "dados": {
            "total_alunos":   total_alunos,
            "total_cursos":   total_cursos,
            "total_usuarios": total_usuarios,
        }
    }


# ════════════════════════════════════════════════════════
#  PONTO DE ENTRADA  — rodar com: python main.py
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
