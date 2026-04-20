from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Alerta,
    EncaminhamentoReuniao,
    Empresa,
    HistoricoAlteracao,
    Iniciativa,
    ObjetivoEstrategico,
    PlanoAcao,
    Reuniao,
    Tarefa,
    Usuario,
)


class PlanoAcaoInline(admin.TabularInline):
    model = PlanoAcao
    extra = 0


class TarefaInline(admin.TabularInline):
    model = Tarefa
    extra = 0


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ativa", "criada_em")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Dados da empresa", {"fields": ("empresa", "perfil", "cargo")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "empresa", "perfil", "is_staff")
    list_filter = ("empresa", "perfil", "is_staff", "is_superuser", "is_active")


@admin.register(ObjetivoEstrategico)
class ObjetivoEstrategicoAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "criado_em")
    list_filter = ("empresa",)
    search_fields = ("nome", "descricao")


@admin.register(Iniciativa)
class IniciativaAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "objetivo", "status", "data_inicio", "data_fim", "responsavel")
    list_filter = ("empresa", "status")
    search_fields = ("nome", "descricao")
    inlines = [TarefaInline]


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ("nome", "iniciativa", "status", "data_vencimento", "responsavel")
    list_filter = ("iniciativa__empresa", "status")
    search_fields = ("nome",)
    inlines = [PlanoAcaoInline]


@admin.register(PlanoAcao)
class PlanoAcaoAdmin(admin.ModelAdmin):
    list_display = ("etapa", "tarefa", "status", "responsavel", "data_inicio_prevista", "data_fim_prevista")
    list_filter = ("tarefa__iniciativa__empresa", "status")
    search_fields = ("etapa", "observacoes")


class EncaminhamentoReuniaoInline(admin.TabularInline):
    model = EncaminhamentoReuniao
    extra = 0


@admin.register(Reuniao)
class ReuniaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empresa", "data_hora", "status", "criada_por")
    list_filter = ("empresa", "status")
    search_fields = ("titulo", "pauta", "ata", "decisoes")
    inlines = [EncaminhamentoReuniaoInline]


@admin.register(EncaminhamentoReuniao)
class EncaminhamentoReuniaoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "reuniao", "tipo_geracao", "responsavel", "prazo")
    list_filter = ("reuniao__empresa", "tipo_geracao")
    search_fields = ("descricao", "detalhes", "reuniao__titulo")


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empresa", "usuario", "lido", "criado_em")
    list_filter = ("empresa", "lido")
    search_fields = ("titulo", "mensagem", "usuario__username")


@admin.register(HistoricoAlteracao)
class HistoricoAlteracaoAdmin(admin.ModelAdmin):
    list_display = ("entidade_nome", "entidade_tipo", "campo", "usuario", "criado_em")
    list_filter = ("empresa", "entidade_tipo", "campo")
    search_fields = ("entidade_nome", "campo", "valor_anterior", "valor_novo")
