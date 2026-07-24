"""Acesso a dados da tabela users."""

import secrets
from typing import Optional

import psycopg

from app.config import ADMIN_EMAILS
from app.db import _pg_conninfo
from app.security import hash_senha

_USER_COLS = ["id", "email", "senha_hash", "nivel", "memoria", "role", "must_change_senha"]


def _row_to_user(row) -> dict:
    return dict(zip(_USER_COLS, row))


def buscar_usuario_por_email(email: str) -> Optional[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, senha_hash, nivel, memoria, role, must_change_senha FROM users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
    return _row_to_user(row) if row else None


def buscar_usuario_por_id(user_id: int) -> Optional[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, senha_hash, nivel, memoria, role, must_change_senha FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return _row_to_user(row) if row else None


def criar_usuario(
    email: str,
    senha_hash: str,
    nivel: str,
    role: str = "engineer",
    must_change_senha: bool = True,
) -> int:
    # must_change_senha=True por padrão: a senha nasce escolhida pela TI/bootstrap,
    # não pelo próprio usuário — ele é obrigado a trocá-la no primeiro login.
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, senha_hash, nivel, role, must_change_senha) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (email, senha_hash, nivel, role, must_change_senha),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    return user_id


def promover_se_admin(usuario: dict) -> None:
    """Promove a conta a admin se o email estiver em ADMIN_EMAILS."""
    if usuario["email"].lower() in ADMIN_EMAILS and usuario.get("role") != "admin":
        with psycopg.connect(_pg_conninfo()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET role = 'admin' WHERE id = %s", (usuario["id"],)
                )
            conn.commit()
        usuario["role"] = "admin"


def seed_admins() -> None:
    """Bootstrap: cria contas admin para ADMIN_EMAILS que ainda não existem,
    com senha temporária impressa no log (o autocadastro está desabilitado)."""
    for email in ADMIN_EMAILS:
        try:
            if buscar_usuario_por_email(email):
                continue
            temp = secrets.token_urlsafe(12)
            criar_usuario(email, hash_senha(temp), "pleno", "admin")
            print(
                f"[bootstrap] admin criado: {email} — senha temporária: {temp} "
                "(troque no painel /admin após o login)"
            )
        except Exception as e:  # Postgres pode não estar pronto ainda
            print(f"[bootstrap] não foi possível semear admin {email}: {e}")


def listar_usuarios() -> list[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, nivel, role, criado_em FROM users ORDER BY id"
            )
            linhas = [
                {
                    "id": r[0],
                    "email": r[1],
                    "nivel": r[2],
                    "role": r[3],
                    "criado_em": r[4].isoformat(),
                }
                for r in cur.fetchall()
            ]
    return linhas


def atualizar_usuario(
    user_id: int,
    email: Optional[str] = None,
    nivel: Optional[str] = None,
    role: Optional[str] = None,
) -> None:
    campos, valores = [], []
    if email is not None:
        campos.append("email = %s")
        valores.append(email)
    if nivel is not None:
        campos.append("nivel = %s")
        valores.append(nivel)
    if role is not None:
        campos.append("role = %s")
        valores.append(role)
    if not campos:
        return
    valores.append(user_id)
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {', '.join(campos)} WHERE id = %s", tuple(valores)
            )
        conn.commit()


def atualizar_senha(user_id: int, senha_hash: str, must_change_senha: bool = True) -> None:
    # must_change_senha=True quando a TI reseta a senha de outra pessoa (padrão);
    # o próprio usuário trocando a senha passa False para liberar o acesso normal.
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET senha_hash = %s, must_change_senha = %s WHERE id = %s",
                (senha_hash, must_change_senha, user_id),
            )
        conn.commit()


def excluir_usuario(user_id: int) -> bool:
    # Sessões/mensagens/log de cache do usuário caem junto via ON DELETE CASCADE.
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def atualizar_memoria(user_id: int, memoria: str) -> None:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET memoria = %s WHERE id = %s", (memoria, user_id)
            )
        conn.commit()
