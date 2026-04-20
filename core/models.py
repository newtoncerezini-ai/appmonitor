from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Empresa(models.Model):
    nome = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class PerfilUsuario(models.TextChoices):
    ADMIN_EMPRESA = "admin_empresa", "Administrador da empresa"
    CONSULTOR = "consultor", "Consultor"
    GESTOR = "gestor", "Gestor"
    COLABORADOR = "colaborador", "Colaborador"


class StatusWorkflow(models.TextChoices):
    NAO_INICIADO = "nao_iniciado", "Nao iniciado"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    CONCLUIDO = "concluido", "Concluido"
    ATRASADO = "atrasado", "Atrasado"
    BLOQUEADO = "bloqueado", "Bloqueado"


class StatusReuniao(models.TextChoices):
    PLANEJADA = "planejada", "Planejada"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    FINALIZADA = "finalizada", "Finalizada"


class TipoGeracaoEncaminhamento(models.TextChoices):
    INICIATIVA = "iniciativa", "Iniciativa"
    TAREFA = "tarefa", "Tarefa"


class TipoEntidadeHistorico(models.TextChoices):
    OBJETIVO = "objetivo", "Objetivo"
    INICIATIVA = "iniciativa", "Iniciativa"
    TAREFA = "tarefa", "Tarefa"
    PLANO_ACAO = "plano_acao", "Plano de acao"
    REUNIAO = "reuniao", "Reuniao"


class Usuario(AbstractUser):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="usuarios",
        null=True,
        blank=True,
    )
    perfil = models.CharField(
        max_length=20,
        choices=PerfilUsuario.choices,
        default=PerfilUsuario.COLABORADOR,
    )
    cargo = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def pode_gerenciar_execucao(self):
        return self.perfil in {
            PerfilUsuario.ADMIN_EMPRESA,
            PerfilUsuario.CONSULTOR,
            PerfilUsuario.GESTOR,
        }


class ObjetivoEstrategico(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="objetivos_estrategicos",
    )
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Objetivo estrategico"
        verbose_name_plural = "Objetivos estrategicos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Iniciativa(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="iniciativas",
    )
    objetivo = models.ForeignKey(
        ObjetivoEstrategico,
        on_delete=models.CASCADE,
        related_name="iniciativas",
    )
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusWorkflow.choices,
        default=StatusWorkflow.NAO_INICIADO,
    )
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="iniciativas_responsavel",
    )
    dependencias = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="desbloqueia_iniciativas",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Iniciativa"
        verbose_name_plural = "Iniciativas"
        ordering = ["data_fim", "nome"]

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        if self.pk and self.dependencias.filter(pk=self.pk).exists():
            raise ValidationError({"dependencias": "Uma iniciativa nao pode depender dela mesma."})

    def atualizar_status_automatico(self, salvar=True):
        tarefas = self.tarefas.all()
        status_anterior = self.status
        novo_status = self.status
        if tarefas.exists() and not tarefas.exclude(status=StatusWorkflow.CONCLUIDO).exists():
            novo_status = StatusWorkflow.CONCLUIDO
        elif self.data_fim and self.data_fim < timezone.localdate():
            novo_status = StatusWorkflow.ATRASADO
        elif tarefas.filter(status=StatusWorkflow.EM_ANDAMENTO).exists():
            novo_status = StatusWorkflow.EM_ANDAMENTO
        elif tarefas.exists():
            novo_status = StatusWorkflow.NAO_INICIADO

        self.status = novo_status
        if salvar:
            self.__class__.objects.filter(pk=self.pk).update(
                status=novo_status,
                atualizada_em=timezone.now(),
            )
            if novo_status != status_anterior:
                registrar_historico_sistema(
                    empresa=self.empresa,
                    entidade_tipo=TipoEntidadeHistorico.INICIATIVA,
                    entidade_id=self.pk,
                    entidade_nome=self.nome,
                    campo="Status",
                    valor_anterior=dict(StatusWorkflow.choices).get(status_anterior, status_anterior),
                    valor_novo=dict(StatusWorkflow.choices).get(novo_status, novo_status),
                )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.pk:
            self.atualizar_status_automatico()


class Tarefa(models.Model):
    iniciativa = models.ForeignKey(
        Iniciativa,
        on_delete=models.CASCADE,
        related_name="tarefas",
    )
    nome = models.CharField(max_length=255)
    responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tarefas_responsavel",
    )
    data_vencimento = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusWorkflow.choices,
        default=StatusWorkflow.NAO_INICIADO,
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"
        ordering = ["data_vencimento", "nome"]

    def __str__(self):
        return self.nome

    @property
    def empresa(self):
        return self.iniciativa.empresa

    def atualizar_status_automatico(self, salvar=True):
        etapas = self.planos_acao.all()
        status_anterior = self.status
        novo_status = self.status
        if etapas.exists() and not etapas.exclude(status=StatusWorkflow.CONCLUIDO).exists():
            novo_status = StatusWorkflow.CONCLUIDO
        elif self.data_vencimento and self.data_vencimento < timezone.localdate():
            novo_status = StatusWorkflow.ATRASADO
        elif etapas.filter(status=StatusWorkflow.EM_ANDAMENTO).exists():
            novo_status = StatusWorkflow.EM_ANDAMENTO
        elif etapas.exists():
            novo_status = StatusWorkflow.NAO_INICIADO

        self.status = novo_status
        if salvar:
            self.__class__.objects.filter(pk=self.pk).update(
                status=novo_status,
                atualizada_em=timezone.now(),
            )
            if novo_status != status_anterior:
                registrar_historico_sistema(
                    empresa=self.empresa,
                    entidade_tipo=TipoEntidadeHistorico.TAREFA,
                    entidade_id=self.pk,
                    entidade_nome=self.nome,
                    campo="Status",
                    valor_anterior=dict(StatusWorkflow.choices).get(status_anterior, status_anterior),
                    valor_novo=dict(StatusWorkflow.choices).get(novo_status, novo_status),
                )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.iniciativa.atualizar_status_automatico()


class PlanoAcao(models.Model):
    tarefa = models.ForeignKey(
        Tarefa,
        on_delete=models.CASCADE,
        related_name="planos_acao",
    )
    etapa = models.CharField(max_length=255)
    responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etapas_responsavel",
    )
    data_inicio_prevista = models.DateField(null=True, blank=True)
    data_inicio_efetiva = models.DateField(null=True, blank=True)
    data_fim_prevista = models.DateField(null=True, blank=True)
    data_fim_efetiva = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusWorkflow.choices,
        default=StatusWorkflow.NAO_INICIADO,
    )
    observacoes = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plano de acao"
        verbose_name_plural = "Planos de acao"
        ordering = ["data_fim_prevista", "etapa"]

    def __str__(self):
        return self.etapa

    def save(self, *args, **kwargs):
        if self.status == StatusWorkflow.CONCLUIDO and not self.data_fim_efetiva:
            self.data_fim_efetiva = timezone.localdate()
        if self.status == StatusWorkflow.EM_ANDAMENTO and not self.data_inicio_efetiva:
            self.data_inicio_efetiva = timezone.localdate()
        super().save(*args, **kwargs)
        self.tarefa.atualizar_status_automatico()
        self.tarefa.iniciativa.atualizar_status_automatico()

    def delete(self, *args, **kwargs):
        tarefa = self.tarefa
        iniciativa = tarefa.iniciativa
        super().delete(*args, **kwargs)
        tarefa.atualizar_status_automatico()
        iniciativa.atualizar_status_automatico()


class Reuniao(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="reunioes",
    )
    titulo = models.CharField(max_length=255)
    data_hora = models.DateTimeField(default=timezone.now)
    local = models.CharField(max_length=180, blank=True)
    participantes = models.TextField(blank=True)
    participantes_usuarios = models.ManyToManyField(
        Usuario,
        blank=True,
        related_name="reunioes_participante",
    )
    participantes_externos = models.TextField(blank=True)
    pauta = models.TextField(blank=True)
    ata = models.TextField(blank=True)
    decisoes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusReuniao.choices,
        default=StatusReuniao.PLANEJADA,
    )
    criada_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reunioes_criadas",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reuniao"
        verbose_name_plural = "Reunioes"
        ordering = ["-data_hora", "titulo"]

    def __str__(self):
        return self.titulo


class EncaminhamentoReuniao(models.Model):
    reuniao = models.ForeignKey(
        Reuniao,
        on_delete=models.CASCADE,
        related_name="encaminhamentos",
    )
    descricao = models.CharField(max_length=255)
    detalhes = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encaminhamentos_reuniao",
    )
    prazo = models.DateField(null=True, blank=True)
    tipo_geracao = models.CharField(
        max_length=20,
        choices=TipoGeracaoEncaminhamento.choices,
        default=TipoGeracaoEncaminhamento.TAREFA,
    )
    objetivo = models.ForeignKey(
        ObjetivoEstrategico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encaminhamentos_reuniao",
    )
    iniciativa_base = models.ForeignKey(
        Iniciativa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encaminhamentos_reuniao",
    )
    iniciativa_gerada = models.ForeignKey(
        Iniciativa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encaminhamentos_origem_reuniao",
    )
    tarefa_gerada = models.ForeignKey(
        Tarefa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encaminhamentos_origem_reuniao",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Encaminhamento de reuniao"
        verbose_name_plural = "Encaminhamentos de reuniao"
        ordering = ["prazo", "descricao"]

    def __str__(self):
        return self.descricao

    @property
    def ja_gerado(self):
        return bool(self.iniciativa_gerada_id or self.tarefa_gerada_id)


class Alerta(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="alertas",
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="alertas",
    )
    titulo = models.CharField(max_length=255)
    mensagem = models.TextField()
    lido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo


class HistoricoAlteracao(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="historicos_alteracao",
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historicos_alteracao",
    )
    entidade_tipo = models.CharField(
        max_length=20,
        choices=TipoEntidadeHistorico.choices,
    )
    entidade_id = models.PositiveIntegerField()
    entidade_nome = models.CharField(max_length=255)
    campo = models.CharField(max_length=120)
    valor_anterior = models.TextField(blank=True)
    valor_novo = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historico de alteracao"
        verbose_name_plural = "Historicos de alteracao"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_entidade_tipo_display()} {self.entidade_nome} - {self.campo}"


def registrar_historico_sistema(empresa, entidade_tipo, entidade_id, entidade_nome, campo, valor_anterior, valor_novo):
    HistoricoAlteracao.objects.create(
        empresa=empresa,
        usuario=None,
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
        entidade_nome=entidade_nome,
        campo=campo,
        valor_anterior=valor_anterior,
        valor_novo=valor_novo,
    )
