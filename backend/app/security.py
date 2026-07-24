"""Hash e verificação de senha (bcrypt). Sem dependências de outros módulos
do app — mantido separado de app/deps.py para evitar import circular
(repositories/users.py precisa de hash_senha; deps.py precisa de
repositories/users.py)."""

import bcrypt


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except ValueError:
        return False
