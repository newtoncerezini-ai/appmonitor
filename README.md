# Sistema de Monitoramento

Projeto Django pensado para consultorias que precisam deixar um sistema simples de acompanhamento rodando dentro de cada empresa atendida.

## Stack recomendada

- Backend: Python + Django
- Banco inicial: SQLite para MVP
- Evolucao natural: PostgreSQL em producao
- Hospedagem sugerida: Railway, Render ou VPS simples com Docker

## Estrutura atual

- `Empresa`: separa os dados de cada cliente
- `Usuario`: login com vinculo a empresa e perfil de acesso
- `ObjetivoEstrategico`
- `Iniciativa`
- `Tarefa`
- `PlanoAcao`
- `Alerta`

## Regras automaticas implementadas

- Se todas as etapas do plano de acao forem concluidas, a tarefa e concluida automaticamente
- Se todas as tarefas da iniciativa forem concluidas, a iniciativa e concluida automaticamente
- Se uma etapa for marcada como `em_andamento`, a data de inicio efetiva e preenchida automaticamente
- Se uma etapa for marcada como `concluido`, a data de fim efetiva e preenchida automaticamente
- Existe um comando para gerar alertas de tarefas e etapas proximas do vencimento

## Telas iniciais

- Login com usuario e senha
- Dashboard do colaborador com:
  - minhas tarefas
  - minhas etapas
  - alertas de vencimento
  - iniciativas em andamento
- Tela de detalhe da tarefa com visualizacao do plano de acao
- Admin do Django para cadastro rapido e operacao do sistema

## Como rodar

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abra:

- `http://127.0.0.1:8000/login/`
- `http://127.0.0.1:8000/admin/`

## Geracao de alertas

```bash
python manage.py gerar_alertas
```

Esse comando foi pensado para ser executado diariamente por um agendador do servidor.

## Proximos passos recomendados

- Definir a hierarquia fina de perfis e permissoes
- Enviar alertas por e-mail ou WhatsApp
- Criar filtros por empresa no admin para usuarios nao superadmin
- Trocar SQLite por PostgreSQL ao publicar
- Criar API e app mobile no futuro, se fizer sentido

## Deploy no Railway

Arquivos ja preparados no projeto:

- `requirements.txt`
- `Procfile`
- `railway.json`

### Variaveis de ambiente recomendadas

- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS=.up.railway.app`
- `CSRF_TRUSTED_ORIGINS=https://SEU_APP.up.railway.app`

### Passo a passo

1. Suba este projeto para um repositorio no GitHub.
2. No Railway, crie um novo projeto a partir do repositorio.
3. Adicione um banco `PostgreSQL` no mesmo projeto.
4. O Railway vai disponibilizar `DATABASE_URL` automaticamente para o servico, ou voce pode mapear essa variavel manualmente.
5. Configure as variaveis de ambiente acima no servico web.
6. Faça o deploy.
7. Depois do primeiro deploy, acesse a URL publica gerada pelo Railway.

### Criar o primeiro superusuario no Railway

Abra o shell do servico e rode:

```bash
python manage.py createsuperuser
```

### Observacoes

- O projeto ja esta configurado para usar PostgreSQL quando `DATABASE_URL` estiver presente.
- Em producao, os arquivos estaticos sao coletados automaticamente.
- O unico aviso esperado em `check --deploy` antes de configurar o Railway e a falta de `SECRET_KEY` segura no ambiente.
