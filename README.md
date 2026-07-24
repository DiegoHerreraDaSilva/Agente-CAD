# Agente CAD/NX — POC

Prova de conceito de um agente **consultivo** de engenharia CAD/Siemens NX, com:

- **Login e gestão de usuários** com autenticação no PostgreSQL (email/senha, hash bcrypt), papéis (engenheiro/admin) e troca de senha obrigatória no primeiro acesso.
- **Chat com streaming** da API do Claude (backend FastAPI + SSE), com sessões persistidas e sidebar de conversas.
- **Três camadas de memória**: curto prazo (histórico da sessão), pessoal (por usuário, editável no Perfil) e compartilhada (base de conhecimento da equipe).
- **Compactação de sessão** (`/compact`): resume a conversa via Claude, libera contexto e envia o resumo como proposta de conhecimento compartilhado (fila de aprovação).
- **Prompt caching**: o system prompt é montado em blocos cacheáveis, reduzindo custo/latência em conversas longas.
- **Painel de administração** (TI): gestão de usuários (criar, editar, resetar senha, excluir), aprovação/rejeição/edição/exclusão/criação manual de entradas na base de conhecimento (com busca), e visão de economia de prompt caching.
- **Anexos no chat**: colar (Ctrl+V) ou anexar imagens, enviadas para a API de visão do Claude junto da pergunta.
- **Interface moderna** (React + Framer Motion + lucide-react): animações de entrada/hover/clique, cantos arredondados sutis, estados vazios/loading tratados, e botão de copiar em cada resposta do agente.

O agente é **estritamente consultivo** — não executa nada no NX. Modelo usado: `claude-haiku-4-5`.

## Stack

Backend em Python (FastAPI + Uvicorn), streaming via SSE, SDK oficial `anthropic`. Banco PostgreSQL 16 rodando em Docker (só o banco — o backend roda em venv local). Frontend em **React + TypeScript (Vite)**, com `react-router-dom` para navegação client-side. Em produção, o build estático (`frontend/dist`) é servido pelo próprio FastAPI — um único processo, como antes. O backend usa o pacote `truststore` para confiar no certificado da rede corporativa ao chamar a API da Anthropic (rede com inspeção TLS).

> O frontend já foi HTML/CSS/JS puro (sem Node), porque a rede corporativa bloqueava `npm install`. Esse bloqueio foi resolvido depois (certificado corporativo liberado para o npm) e o frontend foi migrado para React visando performance (bundles minificados, code-splitting do painel admin via `React.lazy`) e organização de pastas (componentes/hooks/lib em vez de um `<script>` inline por página).

## Pré-requisitos

- Python 3.10+
- Node.js 18+ e npm (para o build do frontend)
- Docker Desktop (para o Postgres)
- Uma chave da API Anthropic
- Um navegador (a interface é servida pelo próprio backend)

## Passo a passo

### 1. Postgres (Docker)

```bash
cd backend
cp .env.example .env          # no Windows PowerShell: copy .env.example .env
# edite o .env: ANTHROPIC_API_KEY, POSTGRES_PASSWORD, SESSION_SECRET e ADMIN_EMAILS
docker compose up -d          # sobe o Postgres e roda init.sql
```

Gere um `SESSION_SECRET` aleatório:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`ADMIN_EMAILS` é uma lista de emails (separados por vírgula) que viram admin automaticamente. Se a conta ainda não existir, o backend a cria no startup com uma senha temporária impressa no log.

### 2. Backend (venv local)

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # Linux/macOS
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

O backend garante o schema do banco no startup (idempotente — não precisa recriar o volume Docker ao atualizar o código).

### 3. Frontend (React + Vite)

**Produção / uso normal** — gera o build estático e deixa o próprio FastAPI servir tudo:

```bash
cd frontend
npm install
npm run build            # gera frontend/dist — o FastAPI passa a servir a partir daqui
```

Depois disso, abra **http://localhost:8000/** — é a única porta usada, front e back juntos.

**Desenvolvimento** — com o backend já rodando em `:8000` (passo 2), roda o Vite em paralelo com hot-reload:

```bash
cd frontend
npm run dev               # abre em http://localhost:5173, com proxy de /auth,/chat,/sessions,/admin,/knowledge para :8000
```

Sem sessão válida, você é redirecionado para `/login`. **Não há autocadastro** — contas são criadas pela TI no painel `/admin` (ou nascem via `ADMIN_EMAILS` no bootstrap). Toda conta nova exige troca de senha no primeiro login.

## Arquitetura

### Organização de pastas

```
nx-agent-poc/
├── public/logo.png              # logo original (fonte); frontend/public/logo.png é uma cópia p/ o Vite
├── backend/
│   ├── main.py                  # composition root: cria o app, inclui os routers, SPA fallback
│   ├── init.sql                 # schema para instalação nova (volume Docker do zero)
│   ├── docker-compose.yml       # só o serviço Postgres
│   ├── requirements.txt
│   ├── .env / .env.example
│   └── app/
│       ├── config.py            # constantes, client Anthropic, paths, ADMIN_EMAILS, truststore
│       ├── db.py                # conexão Postgres + garantir_schema()
│       ├── schemas.py            # modelos Pydantic de request
│       ├── security.py            # hash/verificação de senha (bcrypt)
│       ├── deps.py                 # dependências de auth do FastAPI (usuario_atual, admin_atual...)
│       ├── prompt.py                # montagem do system prompt + validação de imagens
│       ├── repositories/              # acesso a dados: users.py, sessions.py, knowledge.py
│       └── routers/                    # rotas por área: pages, auth, admin, sessions, knowledge, chat
└── frontend/
    ├── vite.config.ts           # proxy de dev para o FastAPI (:8000)
    ├── public/logo.png
    ├── dist/                    # build de produção (gerado, servido pelo FastAPI)
    └── src/
        ├── main.tsx, App.tsx    # entry point + rotas (react-router)
        ├── styles/global.css    # paleta Schwaben (variáveis CSS), portada 1:1 da versão HTML
        ├── lib/                 # api.ts (wrappers tipados de cada endpoint), types.ts, markdown.tsx
        ├── hooks/                # useChatStream, use401Redirect
        ├── context/AuthContext.tsx
        ├── components/
        │   ├── auth/            # RequireAuth, RequireSenhaAtualizada, RequireAdmin (guards de rota)
        │   ├── layout/           # Header
        │   ├── chat/             # Sidebar, MessageBubble, ChatInput (paste/anexo), ResumoBox
        │   ├── modal/            # PerfilModal
        │   └── admin/            # UsersTab, CacheTab, KnowledgeTab, modais de usuário
        └── pages/                # LoginPage, ChangePasswordPage, ChatPage, AdminPage
```

Backend: separado em `app/config.py` → `db.py`/`schemas.py` → `security.py`/`deps.py`/`prompt.py` → `repositories/` (acesso a dados) → `routers/` (rotas), sem framework de camadas nem ORM (`repositories/*.py` são só funções com SQL cru via `psycopg`). `main.py` fica fino: cria o `FastAPI()`, registra os middlewares, inclui cada router e cuida do fallback de SPA — que **precisa** continuar definido ali, depois de todo `include_router(...)`, senão "engoliria" as rotas de API. Frontend: organizado por responsabilidade (components/hooks/lib/pages), sem introduzir um framework de UI (Tailwind etc.) — a paleta e as classes CSS da versão HTML anterior foram portadas como estão.

### Modelo de dados (Postgres)

```
users                    chat_sessions              chat_messages
├─ id (PK)                ├─ id (PK)                  ├─ id (PK)
├─ email (unique)         ├─ user_id (FK→users)       ├─ session_id (FK→chat_sessions)
├─ senha_hash (bcrypt)    ├─ titulo                    ├─ papel ('user'|'assistant')
├─ nivel (enum)           ├─ resumo (texto, /compact)  ├─ conteudo
├─ role ('engineer'|      ├─ criado_em                 └─ criado_em
│         'admin')        └─ atualizado_em
├─ memoria (texto livre)
├─ must_change_senha
└─ criado_em

knowledge_entries          cache_usage_log
├─ id (PK)                 ├─ id (PK)
├─ titulo                  ├─ session_id (FK)
├─ conteudo                ├─ user_id (FK)
├─ categoria                ├─ input_tokens
├─ criado_por                ├─ cache_creation_input_tokens
└─ criado_em                  ├─ cache_read_input_tokens
                              ├─ output_tokens
                              └─ criado_em
```

FKs de `chat_sessions`, `chat_messages` e `cache_usage_log` são `ON DELETE CASCADE`. O schema é criado tanto em `init.sql` (volume novo) quanto em `garantir_schema()` no startup do app (`CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN IF NOT EXISTS`), então atualizações de código nunca exigem recriar o volume Docker.

### As três camadas de memória

1. **Curto prazo** (por sessão): `chat_messages` — histórico multi-turn da conversa atual.
2. **Pessoal** (por usuário): `users.memoria` — texto livre editável no Perfil, sempre injetado no prompt.
3. **Compartilhada** (da equipe): `knowledge_entries` — base técnica de NX/CAD, injetada no prompt a cada mensagem (só as entradas com `status = 'aprovado'`).

**`/compact`** resume as `chat_messages` da sessão (chamada separada ao Claude), grava em `chat_sessions.resumo` e **apaga** as mensagens antigas — o resumo substitui o detalhe, não convive com ele. Esse resumo também é enviado automaticamente como uma nova linha em `knowledge_entries` com `status = 'pendente'` (categoria `resumo_sessao`) — vira conhecimento compartilhado de fato só depois que um admin aprova na aba **Base de conhecimento** do painel `/admin` (`GET/POST /admin/knowledge...`). Rejeitar **exclui a linha de `knowledge_entries`** (não é uma mudança de status) — o resumo de origem em `chat_sessions.resumo` é uma tabela totalmente separada e nunca é afetado: rejeitar na base de conhecimento não apaga nada do histórico/chat do usuário.

Na aba **Base de conhecimento**, o admin também pode: ver o conteúdo completo de qualquer entrada (pendente ou aprovada) e editá-lo antes de decidir, excluir uma entrada já aprovada (some do prompt na próxima mensagem), buscar por título/conteúdo/categoria/autor, e **criar uma entrada manualmente** (`POST /admin/knowledge`) — que entra direto como `aprovada`, sem passar pela fila de revisão, já que o próprio admin a redigiu.

### Autenticação e autorização

Cadeia de dependências do FastAPI, cada uma envolvendo a anterior:

```
usuario_atual(request)          → lê o cookie de sessão, 401 se inválido
  → requer_senha_atualizada()   → 403 se must_change_senha=True
    → admin_atual()             → 403 se role != 'admin'
```

Cadastro público está **desabilitado** (`POST /auth/register` sempre 403). Contas só nascem via bootstrap (`ADMIN_EMAILS` no `.env`) ou pelo painel `/admin`, e sempre com `must_change_senha=True` — forçando a troca de senha antes de liberar qualquer outra rota. Excluir um usuário (`DELETE /admin/users/{id}`) apaga a conta e, via `ON DELETE CASCADE`, suas sessões/mensagens/log de cache; um admin não pode excluir a própria conta (mesma trava usada para impedir o auto-rebaixamento de papel).

Não há `CORSMiddleware` no backend — front e back sempre são a mesma origem do ponto de vista do navegador (proxy do Vite em dev, mesmo processo FastAPI em produção), então nunca houve necessidade de CORS; adicionar `allow_origins=["*"]` só abriria a API (autenticada por cookie de sessão) para leitura por qualquer site.

`POST /auth/login`, `POST /chat` e `POST /sessions/{id}/compact` têm rate limiting via `slowapi` (`Limiter` em `app/config.py`, registrado em `main.py`) — 5/min, 20/min e 10/min respectivamente. Limite excedido devolve `429`. Armazenamento em memória (adequado para um único processo `uvicorn`; se o app ganhar múltiplas réplicas, precisa migrar para um backend compartilhado, ex. Redis).

A **chave** do limite muda por rota, não só o valor: `/auth/login` é por IP (`get_remote_address` — nesse ponto ainda não há usuário autenticado, então não existe outra opção de chave sem introduzir sinal extra). Já `/chat` e `/compact` são **por usuário logado** (`get_user_or_ip` em `app/config.py`, lê `request.session["user_id"]` — o `SessionMiddleware` roda como middleware ASGI, então a sessão já está disponível antes mesmo do `Depends(...)` da rota resolver). Isso corrige um problema real de rede corporativa com NAT: se fosse por IP, todo mundo atrás do mesmo IP externo da empresa compartilharia o mesmo teto — um punhado de engenheiros conversando ao mesmo tempo esgotaria o limite pra todo mundo. Por usuário, cada engenheiro tem seu próprio teto de 20 mensagens/min e 10 compactações/min, independente de quantas outras pessoas estão atrás do mesmo IP.

### Headers de segurança HTTP

Um middleware em `main.py` (`security_headers`) anexa três headers em toda resposta do backend:

- `X-Content-Type-Options: nosniff` — impede o navegador de tentar reinterpretar o tipo de um arquivo diferente do `Content-Type` declarado.
- `X-Frame-Options: DENY` — impede que o app seja carregado dentro de um `<iframe>` em outro site (proteção contra clickjacking).
- `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'` — bloqueia por padrão qualquer script/estilo/imagem/conexão de origem diferente da própria. `img-src data:` é necessário pelos anexos de imagem colados/anexados no chat (Markdown com `data:` URI); `style-src 'unsafe-inline'` é uma concessão pragmática porque vários componentes React usam `style={{...}}` inline (ex.: `KnowledgeTab`, `UsersTab`) — CSP puro bloquearia isso. Isso funciona como segunda camada de defesa contra XSS: o chat e o resumo de sessão renderizam Markdown → HTML via `dangerouslySetInnerHTML` (`MessageBubble.tsx`, `ResumoBox.tsx`); mesmo que um bug no parser ou uma resposta manipulada do agente injetasse um `<script src="...">`, o CSP bloqueia o carregamento.

Esse header só se aplica quando o **FastAPI** serve a resposta — ou seja, produção (`npm run build` + backend) e as chamadas de API mesmo em dev. Rodando `npm run dev`, o HTML vem direto do Vite em `:5173`, sem passar pelo backend; por isso `frontend/index.html` já tem a mesma política numa tag `<meta http-equiv="Content-Security-Policy">`, que cobre esse caso e é servida também dentro do build de produção (as duas coexistem, sem conflito).

Fora de escopo por enquanto: `Strict-Transport-Security` (HSTS) — só faz sentido quando o app rodar atrás de TLS de verdade (hoje é HTTP local, `https_only=False` no `SessionMiddleware`); ver roadmap.

### Fluxo de uma mensagem de chat

```
POST /chat {session_id, pergunta}
  → valida sessão e login
  → grava a pergunta em chat_messages
  → monta o histórico completo (multi-turn) da sessão
  → busca a base de conhecimento compartilhada (determinística, ORDER BY id)
  → monta o system prompt em blocos cacheáveis:
      [tom por nível] --cache-- [conhecimento compartilhado] --cache-- [memória pessoal] --cache-- [resumo, sem cache]
  → client.messages.stream(..., max_tokens=8192) — streaming SSE token a token
  → ao final: captura uso de tokens (incl. cache) e grava a resposta + o log de cache
```

Erros de sobrecarga/limite da API (mesmo no meio do streaming) são detectados pelo tipo do erro no corpo da resposta e viram uma mensagem amigável no chat, sem derrubar a conexão. `/compact` usa `max_tokens=4096` na chamada não-streaming que gera o resumo — ambos os limites foram calibrados para não cortar respostas longas no meio.

### Prompt caching

O `system` é uma lista de blocos, cada um com `cache_control: {"type": "ephemeral"}` (exceto o resumo, que é volátil por sessão e fica após o último breakpoint para não invalidar os demais). O modelo `claude-haiku-4-5` exige um mínimo de ~4096 tokens acumulados no prefixo para cachear de fato — por isso a base de conhecimento foi populada com conteúdo técnico suficiente para cruzar esse limite. O uso real (tokens lidos/escritos do cache) é logado em `cache_usage_log` e exposto no painel `/admin`, com estimativa de custo e economia, e filtro por usuário.

### Frontend

SPA em React + TypeScript, roteada por `react-router-dom`. A autenticação é resolvida uma vez em `RequireAuth` (busca `/auth/me` e guarda o usuário em `AuthContext`), com guards aninhados que espelham as dependências do backend:

```
RequireAuth            (401 → /login)
  └─ RequireSenhaAtualizada  (must_change_senha → /change-password)
       ├─ ChatPage (rota "/")
       └─ RequireAdmin        (role != admin → /)
            └─ AdminPage (rota "/admin")
```

`ChatPage` usa o hook `useChatStream` para consumir o SSE de `/chat` token a token, `lib/markdown.tsx` para renderizar a resposta (mesmo parser leve da versão anterior, sem dependência externa) e reaproveita a mesma extensão de Markdown para imagens (`![](data:...)`) usada pelos anexos colados/anexados no chat. `AdminPage` carrega `ChatPage`/`AdminPage` via `React.lazy` — o bundle do painel admin só é baixado por quem realmente abre `/admin`.

Build (`npm run build`) gera `frontend/dist`, servido pelo FastAPI: os arquivos JS/CSS ficam em `/assets` (via `StaticFiles`) e qualquer rota que não seja de API cai num fallback que devolve `index.html` — o roteamento de fato acontece no navegador (react-router).

## Como validar

0. `cd frontend && npm run build` antes de subir o backend — sem `frontend/dist`, qualquer rota que não seja de API devolve 404 (`main.py` avisa isso explicitamente).
1. Login sem sessão redireciona para `/login`; cadastro está desabilitado.
2. Primeiro acesso de uma conta nova força a troca de senha em `/change-password`.
3. Streaming de chat funciona; nível e memória pessoal influenciam o tom das respostas.
4. Sessões: criar, renomear, excluir, e o histórico persiste ao recarregar.
5. `/compact` resume e limpa mensagens antigas; a sessão volta a responder a partir do resumo.
6. Painel `/admin`: aba de usuários (criar, editar, resetar senha, excluir — exceto a própria conta), aba de base de conhecimento (aprovar/rejeitar pendências de `/compact`) e aba de economia de cache (com filtro por usuário).
7. `GET /knowledge` (autenticado) lista só a base compartilhada aprovada; `curl -i` sem sessão retorna 401 em qualquer rota protegida.
8. Após `/compact`, a entrada some do prompt do chat até um admin aprová-la em `/admin`; rejeitar exclui a linha de `knowledge_entries` mas não altera `chat_sessions.resumo` — a sessão do usuário continua exibindo o resumo normalmente.
9. Base de conhecimento: editar uma entrada pendente/aprovada, excluir uma aprovada, buscar por texto, e criar uma entrada manualmente (deve aparecer já como "Aprovada").
10. Botão de copiar em mensagens do agente copia o texto para a área de transferência.
11. `curl -i http://localhost:8000/` (rodando o build de produção, não `npm run dev`) mostra `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e `Content-Security-Policy` na resposta; console do navegador sem erros de CSP ao usar o app normalmente (imagens no chat, painel admin).
12. Rate limiting: 6 tentativas seguidas de `POST /auth/login` com senha errada → a 6ª retorna `429`; 21 chamadas seguidas a `POST /chat` → a 21ª retorna `429`; 11 chamadas seguidas a `POST /sessions/{id}/compact` → a 11ª retorna `429`.

## Testes de segurança realizados

Bateria de testes manuais executada pelo DevTools do navegador (Chrome) contra a POC rodando localmente, cobrindo a superfície client-side do app. Todos os testes abaixo passaram. 

### 1. Cookie de sessão (roubo de sessão)

O que testa: se o cookie de sessão pode ser lido por JavaScript malicioso.

Como foi feito: `Application → Cookies → localhost:8000`; conferido o flag `HttpOnly` e o `SameSite` do cookie. Também rodado `document.cookie` no console.

Resultado esperado (obtido): `HttpOnly` marcado e `SameSite` definido; `document.cookie` não retorna o cookie de sessão. Isso garante que, mesmo se houver um XSS na página, o cookie não pode ser exfiltrado via JS.

### 2. Cadeia de autorização por rota (401 / 403)

O que testa: se as rotas protegidas respeitam a cadeia `usuario_atual → requer_senha_atualizada → admin_atual`.

Como foi feito: no console, `fetch('/admin/users').then(r => console.log(r.status))` em três estados de sessão distintos.

Resultado esperado (obtido):

- Sem sessão → `401`.
- Logado como `engineer` (não admin) → `403` (barrado em `admin_atual`).
- Logado com `must_change_senha = true` → `403` em qualquer rota fora de `/change-password` (barrado em `requer_senha_atualizada`).

### 3. Isolamento entre usuários — IDOR (o teste crítico)

O que testa: se o backend confia no `session_id` da requisição sem verificar se ele pertence ao usuário logado (Insecure Direct Object Reference).

Como foi feito: logado como usuário A, capturado o `session_id` de uma conversa dele (via `/sessions` ou URL); logado como usuário B e tentado acessar essa sessão:

```js
fetch('/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ session_id: 'ID_DA_SESSAO_DO_A', pergunta: 'teste' })
})
```

Resultado esperado (obtido): o backend não devolve dados da sessão do usuário A — a checagem `WHERE user_id = usuario_atual.id` está presente. Uma falha aqui seria grave (vazamento de conversa entre usuários), por isso é o ponto mais importante da bateria.

### 4. XSS armazenado em campos livres

O que testa: se conteúdo controlado pelo usuário é renderizado como HTML executável (o parser de Markdown é próprio, em `lib/markdown.tsx`, sem lib de sanitização externa).

Como foi feito: inserido o payload `<img src=x onerror=alert(1)>` (e variações com `<script>`) em três campos livres distintos — título de sessão, memória pessoal (Perfil) e conteúdo de entrada da base de conhecimento (via `/admin`) — e recarregada a tela que exibe cada um.

Resultado esperado (obtido): o payload aparece como texto literal (escapado), sem disparar `alert` nem virar um elemento real no DOM. Confirmado inspecionando o HTML resultante no painel Elements. Testados os três campos separadamente, pois cada um passa por caminho de renderização diferente.

### 5. Exposição da chave de API

O que testa: se a `ANTHROPIC_API_KEY` vaza para o cliente (só o backend pode chamar a API da Anthropic).

Como foi feito: aba `Network` filtrada por `Fetch/XHR`, uso normal do chat, inspeção dos payloads de request/response; e busca global (Ctrl+Shift+F) por `sk-ant` na aba `Sources` (todo o JS servido ao navegador).

Resultado esperado (obtido): nenhuma ocorrência da chave em requests, respostas ou no bundle do frontend. A chave permanece apenas no backend.

### 6. Vazamento de stack trace em erros

O que testa: se um erro de servidor devolve detalhes internos (caminho de arquivo Python, traceback) para o cliente.

Como foi feito: provocado erro proposital com payload inválido para `/chat` (`pergunta` vazia / `session_id` inexistente) e inspecionada a resposta na aba `Network`.

Resultado esperado (obtido): a resposta não expõe stack trace nem caminhos internos — apenas erro tratado.

### 7. Cabeçalhos de resposta HTTP

O que testa: presença dos headers de segurança e ausência de CORS indevido.

Como foi feito: `Network → (request principal) → Headers → Response Headers`, e `curl -i http://localhost:8000/` no build de produção.

Resultado / ações tomadas:

- Detectado `Access-Control-Allow-Origin: *` (CORS aberto) — removido, já que front e back são sempre a mesma origem (proxy do Vite em dev, mesmo processo FastAPI em produção).
- Adicionados via middleware `security_headers` em `main.py`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e uma `Content-Security-Policy` restritiva. Confirmados na resposta com `curl -i` e sem erros de CSP no console durante o uso normal (imagens no chat, painel admin).

### 8. Auditoria de cobertura de auth nas rotas

O que testa: se alguma rota em `routers/` (auth, admin, sessions, knowledge, chat, pages) ficou sem a dependência de auth por esquecimento.

Como foi feito: leitura de todas as 28 rotas registradas nos 6 routers + a cadeia de dependências em `app/deps.py` (`usuario_atual → requer_senha_atualizada → admin_atual`), conferindo se cada uma usa a dependência correta para o que faz.

Resultado: nenhuma rota está desprotegida por esquecimento.

- Toda rota admin usa `admin_atual` (que já embute `requer_senha_atualizada` → `usuario_atual` por dependência encadeada).
- Chat, sessões, `/knowledge` e `/auth/me/memoria` usam `requer_senha_atualizada`.
- `usuario_atual` (mais fraco) só aparece em `/auth/me` e `/auth/change-password` — intencional: precisam funcionar mesmo com `must_change_senha=True`, senão o usuário ficaria travado num loop de 403 sem conseguir trocar a própria senha.
- Rotas realmente públicas (`/auth/register` sempre-403, `/auth/login`, `/auth/logout`, `/logo.png`, `/health`, fallback de SPA) não expõem dado nenhum.
- `sessions.py`/`chat.py` também conferem *ownership* (`sessao_do_usuario` com `WHERE user_id = ...`), não só autenticação — reforça o teste 3 (IDOR).
- Ordem de registro em `main.py` confirmada correta: o fallback de SPA é registrado por último, depois de todos os routers, então não pode "engolir" nenhuma rota de API.

Único ponto estilístico (não é falha): `POST /auth/logout` não tem dependência — chamá-lo deslogado só limpa uma sessão já vazia. Inofensivo, deixado como está.

### 9. Rate limiting

O que testa: se rotas sensíveis a força bruta (`/auth/login`) ou a custo de API (`/chat`, `/compact`) tinham algum limite de requisições.

Como foi feito: adicionada a lib `slowapi` (rate limiter padrão para FastAPI, em memória — adequado aqui pois a POC roda um único processo `uvicorn`, sem réplicas): `POST /auth/login` (5/min, por IP — `get_remote_address`), `POST /chat` (20/min, por usuário logado — `get_user_or_ip`), `POST /sessions/{id}/compact` (10/min, por usuário logado). Testado disparando N+1 requisições seguidas de cada rota via `curl`, e também o cenário de dois usuários diferentes atrás do mesmo IP (simulando NAT corporativo).

Resultado (obtido):

- 6ª tentativa de login seguida → `429` (`{"error": "Rate limit exceeded: 5 per 1 minute"}`) em vez de `401`.
- 21ª chamada seguida a `/chat` (usuário A) → `429`.
- 11ª chamada seguida a `/compact` (usuário A) → `429`.
- **Teste do NAT**: logado como usuário B (mesmo IP/`localhost` do teste de A), imediatamente após A esgotar seus limites de `/chat` e `/compact` — B recebe `200` normalmente em ambas as rotas, confirmando que o limite é por usuário, não por IP compartilhado. `/auth/login` continua por IP (usuário ainda não autenticado nesse ponto) — ver limitação conhecida no roadmap.
- Uso normal do app (poucas mensagens por minuto) não é afetado pelos limites.

### 10. SQL injection

O que testa: se algum ponto do backend monta uma query SQL grudando (concatenação/f-string/`.format()`) valor de input externo direto na string, em vez de usar placeholder (`%s`) com o valor passado à parte para o driver. Diferente dos itens anteriores, **isso não dá pra testar pelo DevTools do navegador** — é uma falha server-side, no código Python; a verificação foi por leitura de código, não por interação em runtime.

Como foi feito: auditadas as 29 chamadas `cur.execute(...)` existentes em `app/repositories/users.py`, `sessions.py` e `knowledge.py` (todo o SQL cru do backend vive majoritariamente ali, via `psycopg`, sem ORM), conferindo se cada uma usa placeholder `%s` com valores passados à parte, ou se algum trecho interpola valor dinâmico direto na string antes do `execute()`. Como placeholder `%s` protege **valores** mas não protege **identificadores** (nome de tabela/coluna) nem palavras-chave SQL (ex.: direção `ASC`/`DESC` de um `ORDER BY`) — esse tipo de coisa exigiria lista branca, não dá pra parametrizar —, foi feita uma segunda passada específica: busca por todas as 7 ocorrências de `ORDER BY` no backend inteiro (`repositories/` + `routers/`, não só o SQL cru dos repositórios) para confirmar que nenhuma coluna nem direção vem de input do cliente.

Resultado: **nenhuma vulnerabilidade encontrada.**

- Toda query com valor dinâmico usa `%s` com os valores passados como tupla separada para `execute()` — nunca concatenados/formatados na própria string SQL.
- Duas queries (`atualizar_usuario` em `users.py` e `editar_conhecimento` em `knowledge.py`) montam a cláusula `SET` dinamicamente via f-string, mas só com fragmentos literais fixos do próprio código (`"email = %s"`, `"titulo = %s"` etc.), escolhidos por `if campo is not None` — nunca a partir de nome de coluna vindo de input externo. Os valores em si sempre passam por `%s`/tupla. É o padrão comum e seguro de "atualizar só os campos informados". Mesmo padrão em `GET /admin/cache-stats` (`admin.py:114-116`, fora de `repositories/`): a f-string ali só escolhe entre duas strings literais fixas (`"WHERE user_id = %s"` ou `""`) conforme `usuario_id` foi passado ou não — nunca monta nome de coluna a partir de input.
- **Não existe nenhuma busca `LIKE`/`ILIKE` no backend** — a busca da base de conhecimento (por título/conteúdo/categoria/autor, na aba Base de Conhecimento) é feita inteiramente no cliente (`.filter()`/`.includes()` em JS sobre os dados já carregados), nunca vira uma query SQL com wildcard no servidor. Isso elimina a superfície de risco mais comum (busca textual com `LIKE '%...%'` montado por concatenação).
- **Nenhuma das 7 ocorrências de `ORDER BY` no backend é dinâmica** — toda coluna e toda direção (`ASC`/`DESC`) usada é um literal fixo escrito no código; não existe endpoint que aceite algo como `?order_by=` ou `?dir=` do cliente. Conferido em `knowledge.py` (3x), `users.py`, `sessions.py` (2x) e `admin.py` (`/cache-stats`).

## Fora de escopo (roadmap)

Login Microsoft/Entra ID, escrita/execução real no NX (NXOpen), log de auditoria de acesso administrativo, MD.evolucao, `Strict-Transport-Security` (HSTS) quando o app rodar atrás de TLS de verdade.

**Limitação conhecida — `/auth/login` por IP em rede com NAT.** Diferente de `/chat`/`/compact`, o rate limit de login (5/min) é por IP porque o usuário ainda não está autenticado nesse ponto — não há `user_id` disponível como chave. Numa rede corporativa onde todo mundo sai pelo mesmo IP externo, isso significa que o teto de 5 tentativas/min é compartilhado pela empresa toda: numa manhã de pico com vários engenheiros logando ao mesmo tempo, alguém pode levar `429` mesmo digitando a senha certa. Mitigações possíveis quando isso incomodar na prática: teto mais folgado, um limite combinado por email tentado (em vez de só por IP), ou CAPTCHA — nenhuma foi implementada agora para não aumentar o escopo da POC além do necessário.
