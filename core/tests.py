from datetime import datetime, timedelta

from django.core import mail
from django.test import override_settings
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch

from .models import (
    Empresa,
    HistoricoAlteracao,
    Iniciativa,
    ObjetivoEstrategico,
    PerfilUsuario,
    PlanoAcao,
    Reuniao,
    ReuniaoParticipanteExterno,
    StatusReuniao,
    StatusWorkflow,
    Tarefa,
    TipoEntidadeHistorico,
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
            email="admin@demo.local",
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

    def test_objetivo_pode_ser_editado_pela_tela_e_gera_historico(self):
        self.client.login(username="objetivo_admin", password="senha123forte")
        response = self.client.post(
            reverse("core:objetivo_update", args=[self.objetivo.pk]),
            {
                "nome": "Crescimento comercial",
                "descricao": "Nova descricao",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.nome, "Crescimento comercial")
        self.assertTrue(
            HistoricoAlteracao.objects.filter(
                entidade_tipo=TipoEntidadeHistorico.OBJETIVO,
                entidade_id=self.objetivo.pk,
            ).exists()
        )


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

    def test_gestor_pode_atualizar_iniciativa_pela_tela(self):
        self.client.login(username="iniciativa_admin", password="senha123forte")
        response = self.client.post(
            reverse("core:iniciativa_update", args=[self.iniciativa.pk]),
            {
                "objetivo": self.objetivo.pk,
                "nome": "Estruturar processos",
                "descricao": "Descricao ajustada",
                "status": StatusWorkflow.EM_ANDAMENTO,
                "data_inicio": "",
                "data_fim": "",
                "responsavel": self.usuario.pk,
                "dependencias": [],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.iniciativa.refresh_from_db()
        self.assertEqual(self.iniciativa.descricao, "Descricao ajustada")
        self.assertTrue(
            HistoricoAlteracao.objects.filter(
                entidade_tipo=TipoEntidadeHistorico.INICIATIVA,
                entidade_id=self.iniciativa.pk,
                campo="Status",
            ).exists()
        )

    def test_tarefa_e_plano_podem_ser_editados_pela_tela(self):
        self.client.login(username="iniciativa_admin", password="senha123forte")
        response_tarefa = self.client.post(
            reverse("core:tarefa_update", args=[self.tarefa.pk]),
            {
                "iniciativa": self.iniciativa.pk,
                "nome": "Mapear rotinas internas",
                "responsavel": self.usuario.pk,
                "data_vencimento": "",
                "status": StatusWorkflow.EM_ANDAMENTO,
            },
        )
        plano = self.tarefa.planos_acao.first()
        response_plano = self.client.post(
            reverse("core:plano_acao_update", args=[plano.pk]),
            {
                "tarefa": self.tarefa.pk,
                "etapa": "Levantar fluxo atual",
                "responsavel": self.usuario.pk,
                "data_inicio_prevista": "",
                "data_inicio_efetiva": "",
                "data_fim_prevista": "",
                "data_fim_efetiva": "",
                "status": StatusWorkflow.EM_ANDAMENTO,
                "observacoes": "Atualizado pela tela",
            },
        )

        self.assertEqual(response_tarefa.status_code, 302)
        self.assertEqual(response_plano.status_code, 302)
        self.tarefa.refresh_from_db()
        plano.refresh_from_db()
        self.assertEqual(self.tarefa.nome, "Mapear rotinas internas")
        self.assertEqual(plano.observacoes, "Atualizado pela tela")
        self.assertTrue(
            HistoricoAlteracao.objects.filter(
                entidade_tipo=TipoEntidadeHistorico.TAREFA,
                entidade_id=self.tarefa.pk,
            ).exists()
        )
        self.assertTrue(
            HistoricoAlteracao.objects.filter(
                entidade_tipo=TipoEntidadeHistorico.PLANO_ACAO,
                entidade_id=plano.pk,
            ).exists()
        )


class ReuniaoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Demo", slug="empresa-demo")
        self.usuario = Usuario.objects.create_user(
            username="reuniao_admin",
            email="admin@demo.local",
            password="senha123forte",
            empresa=self.empresa,
            perfil=PerfilUsuario.ADMIN_EMPRESA,
        )
        self.objetivo = ObjetivoEstrategico.objects.create(
            empresa=self.empresa,
            nome="Crescer operacao",
            descricao="Organizar crescimento.",
        )
        self.iniciativa = Iniciativa.objects.create(
            empresa=self.empresa,
            objetivo=self.objetivo,
            nome="Implantar rotina",
            responsavel=self.usuario,
        )

    def test_cria_reuniao_pela_interface(self):
        self.client.login(username="reuniao_admin", password="senha123forte")
        response = self.client.post(
            reverse("core:reuniao_create"),
            {
                "titulo": "Reuniao semanal",
                "data_hora": "2026-04-20T09:00",
                "local": "Online",
                "participantes_usuarios": [self.usuario.pk],
                "external_nome": ["Cliente externo"],
                "external_email": ["cliente@demo.local"],
                "pauta": "Acompanhar execucao",
                "ata": "Discutimos prioridades.",
                "decisoes": "Manter foco comercial.",
                "status": "em_andamento",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Reuniao.objects.filter(titulo="Reuniao semanal", empresa=self.empresa).exists())
        reuniao = Reuniao.objects.get(titulo="Reuniao semanal", empresa=self.empresa)
        self.assertTrue(reuniao.participantes_usuarios.filter(pk=self.usuario.pk).exists())
        self.assertTrue(
            reuniao.participantes_externos_lista.filter(
                nome="Cliente externo",
                email="cliente@demo.local",
            ).exists()
        )

    def test_edicao_carrega_e_preserva_dados_da_reuniao(self):
        reuniao = Reuniao.objects.create(
            empresa=self.empresa,
            titulo="Reuniao de acompanhamento",
            data_hora=timezone.make_aware(datetime(2026, 4, 20, 9, 30)),
            local="Online",
            criada_por=self.usuario,
            pauta="Revisar prioridades",
            ata="Ata original.",
            decisoes="Decisao original.",
            status="em_andamento",
        )
        reuniao.participantes_usuarios.add(self.usuario)
        ReuniaoParticipanteExterno.objects.create(
            reuniao=reuniao,
            nome="Cliente externo",
            email="cliente@demo.local",
        )

        self.client.login(username="reuniao_admin", password="senha123forte")
        get_response = self.client.get(reverse("core:reuniao_update", args=[reuniao.pk]))

        self.assertContains(get_response, 'value="2026-04-20T09:30"')
        self.assertContains(get_response, "Cliente externo")
        self.assertContains(get_response, "cliente@demo.local")
        self.assertContains(get_response, f'<option value="{self.usuario.pk}" selected>', html=False)

        post_response = self.client.post(
            reverse("core:reuniao_update", args=[reuniao.pk]),
            {
                "titulo": "Reuniao de acompanhamento",
                "data_hora": "2026-04-20T09:30",
                "local": "Online",
                "participantes_usuarios": [self.usuario.pk],
                "external_nome": ["Cliente externo"],
                "external_email": ["cliente@demo.local"],
                "pauta": "Revisar prioridades",
                "ata": "Ata atualizada.",
                "decisoes": "Decisao original.",
                "status": "em_andamento",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        reuniao.refresh_from_db()
        self.assertEqual(timezone.localtime(reuniao.data_hora).strftime("%Y-%m-%dT%H:%M"), "2026-04-20T09:30")
        self.assertTrue(reuniao.participantes_usuarios.filter(pk=self.usuario.pk).exists())
        self.assertTrue(reuniao.participantes_externos_lista.filter(email="cliente@demo.local").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_finaliza_reuniao_e_envia_pdf_para_participantes(self):
        reuniao = Reuniao.objects.create(
            empresa=self.empresa,
            titulo="Reuniao comercial",
            criada_por=self.usuario,
            ata="Resumo da conversa.",
            decisoes="Enviar proposta.",
        )
        reuniao.participantes_usuarios.add(self.usuario)
        ReuniaoParticipanteExterno.objects.create(
            reuniao=reuniao,
            nome="Cliente externo",
            email="cliente@demo.local",
        )

        self.client.login(username="reuniao_admin", password="senha123forte")
        response = self.client.post(reverse("core:reuniao_finalizar_enviar", args=[reuniao.pk]))

        self.assertEqual(response.status_code, 302)
        reuniao.refresh_from_db()
        self.assertEqual(reuniao.status, StatusReuniao.FINALIZADA)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(set(mail.outbox[0].to), {"admin@demo.local", "cliente@demo.local"})
        self.assertEqual(mail.outbox[0].attachments[0][2], "application/pdf")

    @override_settings(
        BREVO_API_KEY="api-key-teste",
        DEFAULT_FROM_EMAIL="Consultoria X <newton.cerezini@gmail.com>",
    )
    @patch("core.services.urlopen")
    def test_finaliza_reuniao_envia_pela_api_brevo_quando_configurada(self, mock_urlopen):
        class FakeResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

        mock_urlopen.return_value = FakeResponse()
        reuniao = Reuniao.objects.create(
            empresa=self.empresa,
            titulo="Reuniao via API",
            criada_por=self.usuario,
        )
        reuniao.participantes_usuarios.add(self.usuario)

        self.client.login(username="reuniao_admin", password="senha123forte")
        response = self.client.post(reverse("core:reuniao_finalizar_enviar", args=[reuniao.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(mock_urlopen.called)

    @override_settings(EMAIL_BACKEND="backend.invalido.EmailBackend")
    def test_erro_no_envio_da_ata_retorna_para_detalhe(self):
        reuniao = Reuniao.objects.create(
            empresa=self.empresa,
            titulo="Reuniao com erro de email",
            criada_por=self.usuario,
        )
        reuniao.participantes_usuarios.add(self.usuario)

        self.client.login(username="reuniao_admin", password="senha123forte")
        response = self.client.post(reverse("core:reuniao_finalizar_enviar", args=[reuniao.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:reuniao_detail", args=[reuniao.pk]))

    def test_get_no_envio_da_ata_retorna_para_detalhe(self):
        reuniao = Reuniao.objects.create(
            empresa=self.empresa,
            titulo="Reuniao por get",
            criada_por=self.usuario,
        )

        self.client.login(username="reuniao_admin", password="senha123forte")
        response = self.client.get(reverse("core:reuniao_finalizar_enviar", args=[reuniao.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:reuniao_detail", args=[reuniao.pk]))

    def test_encaminhamento_gera_tarefa(self):
        reuniao = Reuniao.objects.create(
            empresa=self.empresa,
            titulo="Reuniao de execucao",
            criada_por=self.usuario,
        )
        self.client.login(username="reuniao_admin", password="senha123forte")
        response = self.client.post(
            reverse("core:encaminhamento_reuniao_create", args=[reuniao.pk]),
            {
                "descricao": "Atualizar painel semanal",
                "detalhes": "Consolidar dados de vendas.",
                "responsavel": self.usuario.pk,
                "prazo": "2026-04-30",
                "tipo_geracao": "tarefa",
                "objetivo": "",
                "iniciativa_base": self.iniciativa.pk,
            },
        )
        encaminhamento = reuniao.encaminhamentos.get()
        gerar_response = self.client.post(reverse("core:encaminhamento_gerar_item", args=[encaminhamento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(gerar_response.status_code, 302)
        encaminhamento.refresh_from_db()
        self.assertIsNotNone(encaminhamento.tarefa_gerada)
        self.assertEqual(encaminhamento.tarefa_gerada.nome, "Atualizar painel semanal")

    def test_encaminhamento_gera_iniciativa(self):
        reuniao = Reuniao.objects.create(
            empresa=self.empresa,
            titulo="Reuniao estrategica",
            criada_por=self.usuario,
        )
        self.client.login(username="reuniao_admin", password="senha123forte")
        self.client.post(
            reverse("core:encaminhamento_reuniao_create", args=[reuniao.pk]),
            {
                "descricao": "Criar ritual comercial",
                "detalhes": "Novo ritual semanal de pipeline.",
                "responsavel": self.usuario.pk,
                "prazo": "2026-05-15",
                "tipo_geracao": "iniciativa",
                "objetivo": self.objetivo.pk,
                "iniciativa_base": "",
            },
        )
        encaminhamento = reuniao.encaminhamentos.get()
        response = self.client.post(reverse("core:encaminhamento_gerar_item", args=[encaminhamento.pk]))

        self.assertEqual(response.status_code, 302)
        encaminhamento.refresh_from_db()
        self.assertIsNotNone(encaminhamento.iniciativa_gerada)
        self.assertEqual(encaminhamento.iniciativa_gerada.objetivo, self.objetivo)

# Create your tests here.
