from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import (
    Empresa,
    Iniciativa,
    ObjetivoEstrategico,
    PerfilUsuario,
    PlanoAcao,
    StatusWorkflow,
    Tarefa,
    Usuario,
)


class AutomacaoStatusTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Demo", slug="empresa-demo")
        self.usuario = Usuario.objects.create_user(
            username="responsavel",
            password="senha123forte",
            empresa=self.empresa,
        )
        self.objetivo = ObjetivoEstrategico.objects.create(
            empresa=self.empresa,
            nome="Crescer receita",
            descricao="Aumentar faturamento recorrente.",
        )
        self.iniciativa = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Estruturar comercial",
            responsavel=self.usuario,
        )
        self.tarefa = Tarefa.objects.create(
            iniciativa=self.iniciativa,
            nome="Implantar rotina de follow-up",
            responsavel=self.usuario,
            data_vencimento=timezone.localdate() + timedelta(days=5),
        )

    def test_concluir_etapas_conclui_tarefa(self):
        PlanoAcao.objects.create(
            tarefa=self.tarefa,
            etapa="Criar cadencia",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )
        PlanoAcao.objects.create(
            tarefa=self.tarefa,
            etapa="Treinar equipe",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )

        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.status, StatusWorkflow.CONCLUIDO)

    def test_concluir_tarefas_conclui_iniciativa(self):
        tarefa_2 = Tarefa.objects.create(
            iniciativa=self.iniciativa,
            nome="Padronizar proposta",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )
        PlanoAcao.objects.create(
            tarefa=self.tarefa,
            etapa="Publicar modelo",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )
        tarefa_2.refresh_from_db()
        self.iniciativa.refresh_from_db()

        self.assertEqual(tarefa_2.status, StatusWorkflow.CONCLUIDO)
        self.assertEqual(self.iniciativa.status, StatusWorkflow.CONCLUIDO)


class PermissaoCriacaoTelaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Demo", slug="empresa-demo")
        self.objetivo = ObjetivoEstrategico.objects.create(
            empresa=self.empresa,
            nome="Expandir operacao",
            descricao="Expandir capacidade operacional.",
        )
        self.gestor = Usuario.objects.create_user(
            username="gestor",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.GESTOR,
        )
        self.colaborador = Usuario.objects.create_user(
            username="colab",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.COLABORADOR,
        )

    def test_gestor_pode_criar_iniciativa_pela_tela(self):
        self.client.login(username="gestor", password="senha123forte")
        response = self.client.post(
            reverse("core:iniciativa_create"),
            {
                "objetivo": self.objetivo.pk,
                "nome": "Nova iniciativa",
                "descricao": "Detalhes da iniciativa",
                "status": StatusWorkflow.NAO_INICIADO,
                "data_inicio": "2026-04-15",
                "data_fim": "2026-05-15",
                "responsavel": self.gestor.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Iniciativa.objects.filter(nome="Nova iniciativa", empresa=self.empresa).exists())

    def test_colaborador_nao_pode_criar_iniciativa_pela_tela(self):
        self.client.login(username="colab", password="senha123forte")
        response = self.client.get(reverse("core:iniciativa_create"))

        self.assertEqual(response.status_code, 403)


class IniciativaFiltroViewTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Demo", slug="empresa-demo")
        self.gestor = Usuario.objects.create_user(
            username="gestor_view",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.GESTOR,
        )
        self.colaborador = Usuario.objects.create_user(
            username="colab_view",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.COLABORADOR,
        )
        self.objetivo = ObjetivoEstrategico.objects.create(
            empresa=self.empresa,
            nome="Expansao",
            descricao="Expandir operacao.",
        )
        hoje = timezone.localdate()
        Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Iniciativa em andamento",
            status=StatusWorkflow.EM_ANDAMENTO,
            data_inicio=hoje,
            data_fim=hoje + timedelta(days=5),
            responsavel=self.gestor,
        )
        Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Iniciativa concluida",
            status=StatusWorkflow.CONCLUIDO,
            data_inicio=hoje,
            data_fim=hoje + timedelta(days=20),
            responsavel=self.colaborador,
        )

    def test_filtra_iniciativas_por_status(self):
        self.client.login(username="gestor_view", password="senha123forte")
        response = self.client.get(reverse("core:initiative_list"), {"status": StatusWorkflow.CONCLUIDO})

        self.assertEqual(response.status_code, 200)
        iniciativas = list(response.context["iniciativas"])
        self.assertEqual(len(iniciativas), 1)
        self.assertEqual(iniciativas[0].nome, "Iniciativa concluida")

    def test_modo_quadro_e_exposto_no_contexto(self):
        self.client.login(username="gestor_view", password="senha123forte")
        response = self.client.get(reverse("core:initiative_list"), {"view": "quadro"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_mode"], "quadro")


class DependenciaIniciativaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Demo", slug="empresa-demo")
        self.usuario = Usuario.objects.create_user(
            username="dep_admin",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.ADMIN_EMPRESA,
        )
        self.objetivo = ObjetivoEstrategico.objects.create(
            empresa=self.empresa,
            nome="Organizacao",
            descricao="Organizar execucao.",
        )

    def test_iniciativa_pode_depender_de_outra(self):
        iniciativa_base = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Base",
            responsavel=self.usuario,
        )
        iniciativa_dependente = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Dependente",
            responsavel=self.usuario,
        )
        iniciativa_dependente.dependencias.add(iniciativa_base)

        self.assertIn(iniciativa_base, iniciativa_dependente.dependencias.all())

    def test_lista_de_iniciativas_expoe_total_com_dependencias(self):
        iniciativa_base = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Base",
            responsavel=self.usuario,
        )
        iniciativa_dependente = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Dependente",
            responsavel=self.usuario,
        )
        iniciativa_dependente.dependencias.add(iniciativa_base)
        self.client.login(username="dep_admin", password="senha123forte")

        response = self.client.get(reverse("core:initiative_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_com_dependencias"], 1)


class ObjetivoDetalheTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Demo", slug="empresa-demo")
        self.usuario = Usuario.objects.create_user(
            username="objetivo_admin",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.ADMIN_EMPRESA,
        )
        self.objetivo = ObjetivoEstrategico.objects.create(
            empresa=self.empresa,
            nome="Crescimento",
            descricao="Expandir a operacao com previsibilidade.",
        )
        self.iniciativa = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Estruturar comercial",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )
        Tarefa.objects.create(
            iniciativa=self.iniciativa,
            nome="Mapear pipeline",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )

    def test_detalhe_do_objetivo_exibe_metricas(self):
        self.client.login(username="objetivo_admin", password="senha123forte")
        response = self.client.get(reverse("core:objective_detail", args=[self.objetivo.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["hero_value"], 100)
        self.assertEqual(response.context["hero_secondary"], 1)
        self.assertEqual(response.context["tarefas_total"], 1)

    def test_lista_de_objetivos_expoe_iniciativas_concluidas(self):
        self.client.login(username="objetivo_admin", password="senha123forte")
        response = self.client.get(reverse("core:objective_list"))

        self.assertEqual(response.status_code, 200)
        objetivo = response.context["objetivos"][0]
        self.assertEqual(objetivo.iniciativas_concluidas, 1)


class IniciativaDetalheTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Demo", slug="empresa-demo")
        self.usuario = Usuario.objects.create_user(
            username="iniciativa_admin",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.ADMIN_EMPRESA,
        )
        self.objetivo = ObjetivoEstrategico.objects.create(
            empresa=self.empresa,
            nome="Operacao",
            descricao="Melhorar a execucao.",
        )
        self.iniciativa = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Estruturar processos",
            responsavel=self.usuario,
        )
        self.tarefa = Tarefa.objects.create(
            iniciativa=self.iniciativa,
            nome="Mapear rotinas",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )
        PlanoAcao.objects.create(
            tarefa=self.tarefa,
            etapa="Levantar fluxo atual",
            responsavel=self.usuario,
            status=StatusWorkflow.CONCLUIDO,
        )

    def test_detalhe_da_iniciativa_exibe_metricas_de_tarefas_e_planos(self):
        self.client.login(username="iniciativa_admin", password="senha123forte")
        response = self.client.get(reverse("core:initiative_detail", args=[self.iniciativa.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tarefas_total"], 1)
        self.assertEqual(response.context["tarefas_concluidas"], 1)
        self.assertEqual(response.context["planos_total"], 1)
        self.assertEqual(response.context["progresso_planos"], 100)

# Create your tests here.
