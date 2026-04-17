from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    Empresa,
    Iniciativa,
    ObjetivoEstrategico,
    PerfilUsuario,
    PlanoAcao,
    StatusWorkflow,
    Tarefa,
    Usuario,
)


class Command(BaseCommand):
    help = "Popula o banco com dados ficticios para demonstracao visual do sistema."

    def handle(self, *args, **options):
        hoje = timezone.localdate()

        empresa, _ = Empresa.objects.get_or_create(
            slug="demo",
            defaults={"nome": "Empresa Demo"},
        )

        usuarios = {
            "admin": self._upsert_usuario(
                username="admin",
                empresa=empresa,
                perfil=PerfilUsuario.ADMIN_EMPRESA,
                first_name="Administrador",
                last_name="Demo",
                email="admin@local.test",
                is_staff=True,
                is_superuser=True,
            ),
            "consultor": self._upsert_usuario(
                username="consultor.demo",
                empresa=empresa,
                perfil=PerfilUsuario.CONSULTOR,
                first_name="Marina",
                last_name="Consultora",
                email="consultor@demo.local",
            ),
            "gestor": self._upsert_usuario(
                username="gestor.demo",
                empresa=empresa,
                perfil=PerfilUsuario.GESTOR,
                first_name="Carlos",
                last_name="Gestor",
                email="gestor@demo.local",
            ),
            "colaborador1": self._upsert_usuario(
                username="ana.silva",
                empresa=empresa,
                perfil=PerfilUsuario.COLABORADOR,
                first_name="Ana",
                last_name="Silva",
                email="ana@demo.local",
            ),
            "colaborador2": self._upsert_usuario(
                username="joao.souza",
                empresa=empresa,
                perfil=PerfilUsuario.COLABORADOR,
                first_name="Joao",
                last_name="Souza",
                email="joao@demo.local",
            ),
        }

        objetivo_1, _ = ObjetivoEstrategico.objects.get_or_create(
            empresa=empresa,
            nome="Aumentar a eficiencia comercial",
            defaults={
                "descricao": "Padronizar a operacao comercial para elevar conversao, previsibilidade e cadencia de acompanhamento."
            },
        )
        objetivo_2, _ = ObjetivoEstrategico.objects.get_or_create(
            empresa=empresa,
            nome="Melhorar a execucao operacional",
            defaults={
                "descricao": "Organizar processos internos e indicadores para reduzir atrasos e aumentar a qualidade das entregas."
            },
        )
        objetivo_3, _ = ObjetivoEstrategico.objects.get_or_create(
            empresa=empresa,
            nome="Fortalecer a gestao de pessoas",
            defaults={
                "descricao": "Criar rituais, responsabilidades e acompanhamento das equipes para sustentar o crescimento."
            },
        )

        iniciativa_1 = self._upsert_iniciativa(
            empresa=empresa,
            objetivo=objetivo_1,
            nome="Estruturar funil de vendas",
            descricao="Revisar etapas do funil, rotinas de follow-up e padrao de proposta comercial.",
            status=StatusWorkflow.EM_ANDAMENTO,
            data_inicio=hoje - timedelta(days=20),
            data_fim=hoje + timedelta(days=25),
            responsavel=usuarios["gestor"],
        )
        iniciativa_2 = self._upsert_iniciativa(
            empresa=empresa,
            objetivo=objetivo_2,
            nome="Implantar rotina de acompanhamento semanal",
            descricao="Criar uma rotina gerencial com metas, indicadores e plano de acao semanal.",
            status=StatusWorkflow.EM_ANDAMENTO,
            data_inicio=hoje - timedelta(days=10),
            data_fim=hoje + timedelta(days=18),
            responsavel=usuarios["consultor"],
        )
        iniciativa_3 = self._upsert_iniciativa(
            empresa=empresa,
            objetivo=objetivo_3,
            nome="Organizar onboarding de novos colaboradores",
            descricao="Padronizar integracao inicial e acompanhamento dos primeiros 30 dias.",
            status=StatusWorkflow.NAO_INICIADO,
            data_inicio=hoje + timedelta(days=3),
            data_fim=hoje + timedelta(days=40),
            responsavel=usuarios["admin"],
        )

        tarefa_1 = self._upsert_tarefa(
            iniciativa=iniciativa_1,
            nome="Mapear gargalos do funil atual",
            responsavel=usuarios["consultor"],
            data_vencimento=hoje + timedelta(days=4),
            status=StatusWorkflow.EM_ANDAMENTO,
        )
        tarefa_2 = self._upsert_tarefa(
            iniciativa=iniciativa_1,
            nome="Criar modelo padrao de proposta",
            responsavel=usuarios["colaborador1"],
            data_vencimento=hoje + timedelta(days=9),
            status=StatusWorkflow.NAO_INICIADO,
        )
        tarefa_3 = self._upsert_tarefa(
            iniciativa=iniciativa_2,
            nome="Definir pauta da reuniao semanal",
            responsavel=usuarios["gestor"],
            data_vencimento=hoje + timedelta(days=2),
            status=StatusWorkflow.EM_ANDAMENTO,
        )
        tarefa_4 = self._upsert_tarefa(
            iniciativa=iniciativa_2,
            nome="Construir painel de indicadores",
            responsavel=usuarios["colaborador2"],
            data_vencimento=hoje + timedelta(days=12),
            status=StatusWorkflow.NAO_INICIADO,
        )
        tarefa_5 = self._upsert_tarefa(
            iniciativa=iniciativa_3,
            nome="Desenhar jornada de integracao",
            responsavel=usuarios["admin"],
            data_vencimento=hoje + timedelta(days=20),
            status=StatusWorkflow.NAO_INICIADO,
        )

        self._upsert_plano(
            tarefa=tarefa_1,
            etapa="Levantar dados do CRM e entrevistas com time comercial",
            responsavel=usuarios["consultor"],
            data_inicio_prevista=hoje - timedelta(days=5),
            data_inicio_efetiva=hoje - timedelta(days=5),
            data_fim_prevista=hoje + timedelta(days=1),
            status=StatusWorkflow.EM_ANDAMENTO,
            observacoes="Analise em andamento com foco em taxa de conversao e tempo medio por etapa.",
        )
        self._upsert_plano(
            tarefa=tarefa_1,
            etapa="Consolidar diagnostico e apresentar recomendacoes",
            responsavel=usuarios["gestor"],
            data_inicio_prevista=hoje + timedelta(days=2),
            data_fim_prevista=hoje + timedelta(days=4),
            status=StatusWorkflow.NAO_INICIADO,
            observacoes="Apresentacao prevista para a proxima reuniao executiva.",
        )
        self._upsert_plano(
            tarefa=tarefa_2,
            etapa="Revisar propostas antigas e padroes de precificacao",
            responsavel=usuarios["colaborador1"],
            data_inicio_prevista=hoje + timedelta(days=1),
            data_fim_prevista=hoje + timedelta(days=4),
            status=StatusWorkflow.NAO_INICIADO,
            observacoes="Selecionar os melhores exemplos e unificar linguagem comercial.",
        )
        self._upsert_plano(
            tarefa=tarefa_2,
            etapa="Validar template com diretoria comercial",
            responsavel=usuarios["gestor"],
            data_inicio_prevista=hoje + timedelta(days=5),
            data_fim_prevista=hoje + timedelta(days=9),
            status=StatusWorkflow.NAO_INICIADO,
            observacoes="Considerar ajuste de escopo, precificacao e clausulas padrao.",
        )
        self._upsert_plano(
            tarefa=tarefa_3,
            etapa="Definir indicadores prioritarios da reuniao",
            responsavel=usuarios["gestor"],
            data_inicio_prevista=hoje - timedelta(days=2),
            data_inicio_efetiva=hoje - timedelta(days=2),
            data_fim_prevista=hoje + timedelta(days=1),
            status=StatusWorkflow.EM_ANDAMENTO,
            observacoes="Foco em faturamento, backlog, prazo medio e produtividade.",
        )
        self._upsert_plano(
            tarefa=tarefa_3,
            etapa="Criar ritual de acompanhamento e responsaveis",
            responsavel=usuarios["consultor"],
            data_inicio_prevista=hoje + timedelta(days=1),
            data_fim_prevista=hoje + timedelta(days=2),
            status=StatusWorkflow.NAO_INICIADO,
            observacoes="Definir frequencia, participantes e pauta fixa.",
        )
        self._upsert_plano(
            tarefa=tarefa_4,
            etapa="Montar estrutura inicial do dashboard",
            responsavel=usuarios["colaborador2"],
            data_inicio_prevista=hoje + timedelta(days=3),
            data_fim_prevista=hoje + timedelta(days=7),
            status=StatusWorkflow.NAO_INICIADO,
            observacoes="Versao inicial para validar com a lideranca.",
        )
        self._upsert_plano(
            tarefa=tarefa_5,
            etapa="Listar entregas da primeira semana",
            responsavel=usuarios["admin"],
            data_inicio_prevista=hoje + timedelta(days=8),
            data_fim_prevista=hoje + timedelta(days=10),
            status=StatusWorkflow.NAO_INICIADO,
            observacoes="Incluir treinamento, acessos e acompanhamento inicial.",
        )

        for iniciativa in Iniciativa.objects.filter(empresa=empresa):
            iniciativa.atualizar_status_automatico()

        self.stdout.write(self.style.SUCCESS("Base ficticia criada com sucesso."))

    def _upsert_usuario(self, username, empresa, perfil, first_name, last_name, email, **extra_fields):
        user, created = Usuario.objects.get_or_create(
            username=username,
            defaults={
                "empresa": empresa,
                "perfil": perfil,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                **extra_fields,
            },
        )
        if created and username != "admin":
            user.set_password("123@mudar")
            user.save()

        changed = False
        for field, value in {
            "empresa": empresa,
            "perfil": perfil,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            **extra_fields,
        }.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if changed:
            user.save()
        return user

    def _upsert_iniciativa(self, **kwargs):
        defaults = kwargs.copy()
        nome = defaults.pop("nome")
        empresa = defaults["empresa"]
        iniciativa, _ = Iniciativa.objects.update_or_create(
            empresa=empresa,
            nome=nome,
            defaults=defaults,
        )
        return iniciativa

    def _upsert_tarefa(self, **kwargs):
        defaults = kwargs.copy()
        iniciativa = defaults["iniciativa"]
        nome = defaults.pop("nome")
        tarefa, _ = Tarefa.objects.update_or_create(
            iniciativa=iniciativa,
            nome=nome,
            defaults=defaults,
        )
        return tarefa

    def _upsert_plano(self, **kwargs):
        defaults = kwargs.copy()
        tarefa = defaults["tarefa"]
        etapa = defaults.pop("etapa")
        plano, _ = PlanoAcao.objects.update_or_create(
            tarefa=tarefa,
            etapa=etapa,
            defaults=defaults,
        )
        return plano
