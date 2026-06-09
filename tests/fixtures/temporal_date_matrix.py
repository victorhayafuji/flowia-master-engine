"""Parametric PT-BR colloquial date cases for date_parsing tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from packages.scheduling.date_parsing import DateParseMode


@dataclass(frozen=True)
class TemporalCase:
    id: str
    text: str
    reference: date
    mode: DateParseMode
    expected_iso: str | None
    expected_none_reason: str | None = None
    expected_clarification_reason: str | None = None


REFERENCE = date(2026, 6, 7)  # Sunday
WED = date(2026, 6, 3)
FRIDAY = date(2026, 6, 5)
THU = date(2026, 6, 4)
MON = date(2026, 6, 1)


def _cases() -> tuple[TemporalCase, ...]:
    c: list[TemporalCase] = []

    def add(
        id_: str,
        text: str,
        ref: date,
        mode: DateParseMode,
        iso: str | None,
        *,
        none_reason: str | None = None,
        clarify: str | None = None,
    ) -> None:
        c.append(
            TemporalCase(
                id=id_,
                text=text,
                reference=ref,
                mode=mode,
                expected_iso=iso,
                expected_none_reason=none_reason,
                expected_clarification_reason=clarify,
            )
        )

    # --- relative short ---
    add("rel_hoje", "Tem horário hoje?", REFERENCE, DateParseMode.BOOKING, "2026-06-07")
    add("rel_amanha", "Quero agendar manicure amanhã", REFERENCE, DateParseMode.BOOKING, "2026-06-08")
    add("rel_depois_amanha", "Corte depois de amanhã", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("rel_ontem_booking", "Quero agendar ontem", REFERENCE, DateParseMode.BOOKING, None, none_reason="past")
    add("rel_ontem_ref", "Faltei ontem", REFERENCE, DateParseMode.REFERENCE, "2026-06-06")
    add("rel_depois_ontem_ref", "Faltei depois de ontem", REFERENCE, DateParseMode.REFERENCE, "2026-06-05")
    add("rel_anteontem_ref", "Preciso cancelar o horário de anteontem", REFERENCE, DateParseMode.REFERENCE, "2026-06-05")
    add("rel_anteontem_booking", "Agendar anteontem", REFERENCE, DateParseMode.BOOKING, None, none_reason="past")
    add("rel_hoje_noite", "hoje a noite", REFERENCE, DateParseMode.BOOKING, "2026-06-07")
    add("rel_ontem_tarde_ref", "ontem a tarde", REFERENCE, DateParseMode.REFERENCE, "2026-06-06")
    add("rel_amanha_manha", "amanha de manha", REFERENCE, DateParseMode.BOOKING, "2026-06-08")
    add("rel_amanha_tarde", "amanha de tarde", REFERENCE, DateParseMode.BOOKING, "2026-06-08")

    # --- typos / accents / aliases (P3) ---
    add("typo_amanha", "manicure amanha", REFERENCE, DateParseMode.BOOKING, "2026-06-08")
    add("typo_proxima_sexta", "proxima sexta", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("typo_prox_sexta", "prox sexta", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("typo_pra_sexta", "pra sexta", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("typo_na_sexta", "na sexta", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("typo_sab", "corte sab", REFERENCE, DateParseMode.BOOKING, "2026-06-13")
    add("typo_6f", "6f", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("typo_ter", "ter", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("typo_qta", "qta", REFERENCE, DateParseMode.BOOKING, "2026-06-10")
    add("typo_qna", "qna", REFERENCE, DateParseMode.BOOKING, "2026-06-11")
    add("typo_dom", "dom", REFERENCE, DateParseMode.BOOKING, "2026-06-07")

    # --- weekday ---
    add("wd_sexta", "Quero mechas sexta", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("wd_sexta_same_day", "sexta", FRIDAY, DateParseMode.BOOKING, "2026-06-05")
    add("wd_proxima_sexta_friday", "próxima sexta", FRIDAY, DateParseMode.BOOKING, "2026-06-12")
    add("wd_sexta_passada_ref", "sexta passada", REFERENCE, DateParseMode.REFERENCE, "2026-06-05")
    add("wd_sexta_passada_booking", "sexta passada", REFERENCE, DateParseMode.BOOKING, None, none_reason="past_only")
    add("wd_essa_sexta_ref", "essa sexta", REFERENCE, DateParseMode.REFERENCE, "2026-06-05")
    add("wd_essa_sexta_booking", "essa sexta", REFERENCE, DateParseMode.BOOKING, None, clarify="past_this_week")
    add("wd_neste_sabado_sun", "neste sabado", REFERENCE, DateParseMode.BOOKING, None, clarify="past_this_week")
    add("wd_domingo_que_vem", "domingo que vem", REFERENCE, DateParseMode.BOOKING, "2026-06-14")
    add("wd_terca_feira", "terca-feira", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("wd_leftmost_sabado", "sabado ou sexta", REFERENCE, DateParseMode.BOOKING, None, clarify="multiple_weekdays")
    add("wd_leftmost_sexta_first", "sexta ou sabado", REFERENCE, DateParseMode.BOOKING, None, clarify="multiple_weekdays")
    add("wd_segunda", "segunda", REFERENCE, DateParseMode.BOOKING, "2026-06-08")
    add("wd_quarta", "quarta", REFERENCE, DateParseMode.BOOKING, "2026-06-10")
    add("wd_quinta", "quinta", REFERENCE, DateParseMode.BOOKING, "2026-06-11")
    add("wd_domingo", "domingo", REFERENCE, DateParseMode.BOOKING, "2026-06-07")
    add("wd_proxima_terca", "proxima terca", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("wd_esta_quarta_wed", "esta quarta", WED, DateParseMode.BOOKING, "2026-06-03")

    # --- absolute ---
    add("abs_junho", "12 de junho", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("abs_slash", "10/06/2026", REFERENCE, DateParseMode.BOOKING, "2026-06-10")
    add("abs_slash_short", "10/06", REFERENCE, DateParseMode.BOOKING, "2026-06-10")
    add("abs_iso", "2026-06-15", REFERENCE, DateParseMode.BOOKING, "2026-06-15")
    add("abs_in_text", "Sim, tem horário para 12 de junho?", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("abs_currency_not_date", "Quanto custa? R$ 10/06", REFERENCE, DateParseMode.BOOKING, None, none_reason="price_not_date")
    add("abs_dia_15_jun", "dia 15 de junho", REFERENCE, DateParseMode.BOOKING, "2026-06-15")
    add("abs_dia_15_booking", "dia 15", REFERENCE, DateParseMode.BOOKING, "2026-06-15")
    add("abs_dia_15_ref", "dia 15", REFERENCE, DateParseMode.REFERENCE, None, clarify="day_without_month")
    add("abs_dia_3_booking", "dia 3", REFERENCE, DateParseMode.BOOKING, "2026-07-03")
    add("abs_1_julho", "1 de julho", REFERENCE, DateParseMode.BOOKING, "2026-07-01")

    # --- week phrases ---
    add("week_next", "Preciso ir semana que vem", REFERENCE, DateParseMode.BOOKING, None, clarify="week_without_weekday")
    add("week_next_short", "semana que vem", REFERENCE, DateParseMode.BOOKING, None, clarify="week_without_weekday")
    add("week_next_on_friday", "semana que vem na sexta", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("week_proxima", "proxima semana", REFERENCE, DateParseMode.BOOKING, None, clarify="week_without_weekday")
    add("week_hint_essa", "essa semana", REFERENCE, DateParseMode.BOOKING, None, clarify="week_hint_only")
    add("week_hint_esta", "esta semana", REFERENCE, DateParseMode.BOOKING, None, clarify="week_hint_only")
    add("week_past_ref", "faltei semana passada", REFERENCE, DateParseMode.REFERENCE, "2026-05-25")
    add("week_past_booking", "agendar semana passada", REFERENCE, DateParseMode.BOOKING, None, none_reason="past_only")

    # --- weekend / neste ---
    add("wknd_generic", "corte fim de semana", REFERENCE, DateParseMode.BOOKING, "2026-06-13")
    add("wknd_this", "neste fim de semana", WED, DateParseMode.BOOKING, "2026-06-06")
    add("wknd_neste_sabado_wed", "neste sabado", WED, DateParseMode.BOOKING, "2026-06-06")
    add("wknd_proximo_domingo", "proximo domingo", REFERENCE, DateParseMode.BOOKING, "2026-06-14")
    add("wknd_proximo_fds", "proximo fim de semana", REFERENCE, DateParseMode.BOOKING, "2026-06-13")
    add("wknd_final_semana", "final de semana", REFERENCE, DateParseMode.BOOKING, "2026-06-13")

    # --- numeric offset ---
    add("offset_3d", "daqui a 3 dias", REFERENCE, DateParseMode.BOOKING, "2026-06-10")
    add("offset_daqui_3d", "daqui 3 dias", REFERENCE, DateParseMode.BOOKING, "2026-06-10")
    add("offset_em_3d", "em 3 dias", REFERENCE, DateParseMode.BOOKING, "2026-06-10")
    add("offset_1w", "em 1 semana", REFERENCE, DateParseMode.BOOKING, "2026-06-14")
    add("offset_daqui_1w", "daqui 1 semana", REFERENCE, DateParseMode.BOOKING, "2026-06-14")
    add("offset_2_dias_uteis_sun", "em 2 dias uteis", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("offset_1_dia_util_fri", "em 1 dia util", FRIDAY, DateParseMode.BOOKING, "2026-06-08")
    add("offset_3_dias_uteis_thu", "daqui 3 dias uteis", THU, DateParseMode.BOOKING, "2026-06-09")
    add("offset_5_dias_uteis_mon", "em 5 dias uteis", MON, DateParseMode.BOOKING, "2026-06-08")

    # --- negatives / false positives ---
    add("neg_onde", "Onde fica o salão?", REFERENCE, DateParseMode.REFERENCE, None, none_reason="no_date")
    add("neg_greeting", "Bom dia, tudo bem?", REFERENCE, DateParseMode.BOOKING, None, none_reason="no_date")
    add("neg_contemporaneo", "corte contemporaneo", REFERENCE, DateParseMode.BOOKING, None, none_reason="no_date")
    add("neg_momento", "no momento nao posso", REFERENCE, DateParseMode.BOOKING, None, none_reason="no_date")
    add("neg_outro_dia", "outro dia eu vejo", REFERENCE, DateParseMode.BOOKING, None, none_reason="no_date")
    add("neg_mudar_data", "mudar data", REFERENCE, DateParseMode.BOOKING, None, none_reason="no_date")

    # --- relative + weekday alternatives ---
    THU_JUN11 = date(2026, 6, 11)
    WED_JUN10 = date(2026, 6, 10)
    add(
        "alt_amanha_ou_sexta_clarify",
        "corte masculino para amanha ou sexta",
        WED_JUN10,
        DateParseMode.BOOKING,
        None,
        clarify="multiple_dates",
    )
    add(
        "alt_amanha_ou_sexta_same",
        "corte masculino para amanha ou sexta",
        THU_JUN11,
        DateParseMode.BOOKING,
        "2026-06-12",
    )
    add(
        "alt_amanha_ou_depois_clarify",
        "amanha ou depois de amanha",
        REFERENCE,
        DateParseMode.BOOKING,
        None,
        clarify="multiple_dates",
    )

    # --- ordering ---
    add("order_depois", "depois de amanhã", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("order_depois_manha", "depois de amanha de manha", REFERENCE, DateParseMode.BOOKING, "2026-06-09")

    # --- support + booking phrasing ---
    add("support_cancel_amanha", "cancelar para amanha", REFERENCE, DateParseMode.REFERENCE, "2026-06-08")
    add("support_atraso_hoje", "me atrasei hoje", REFERENCE, DateParseMode.REFERENCE, "2026-06-07")
    add("support_faltei_sexta", "faltei na sexta", REFERENCE, DateParseMode.REFERENCE, "2026-06-12")
    add("support_cancel_semana", "cancelar semana que vem", REFERENCE, DateParseMode.REFERENCE, None, clarify="week_without_weekday")

    # --- reference-only past windows ---
    add("ref_hoje", "compareci hoje", REFERENCE, DateParseMode.REFERENCE, "2026-06-07")
    add("ref_amanha", "vou cancelar amanha", REFERENCE, DateParseMode.REFERENCE, "2026-06-08")
    add("ref_sexta_passada", "atraso da sexta passada", REFERENCE, DateParseMode.REFERENCE, "2026-06-05")

    # --- extra weekday compounds ---
    add("wd_sexta_que_vem", "sexta que vem", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("wd_sabado_passado_ref", "sabado passado", REFERENCE, DateParseMode.REFERENCE, "2026-06-06")
    add("wd_neste_domingo_wed", "neste domingo", WED, DateParseMode.BOOKING, "2026-06-07")
    add("wd_essa_quarta_sun", "essa quarta", REFERENCE, DateParseMode.BOOKING, None, clarify="past_this_week")
    add("wd_esta_sexta_fri", "esta sexta", FRIDAY, DateParseMode.BOOKING, "2026-06-05")

    # --- slash variants ---
    add("abs_slash_yearless_aug", "15/08", REFERENCE, DateParseMode.BOOKING, "2026-08-15")
    add("abs_slash_past_jan", "15/01", REFERENCE, DateParseMode.BOOKING, None, none_reason="past")
    add("abs_slash_in_phrase", "agendar 20/06", REFERENCE, DateParseMode.BOOKING, "2026-06-20")

    # --- daqui/em variants ---
    add("offset_daqui_2d", "daqui 2 dias", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("offset_em_2w", "em 2 semanas", REFERENCE, DateParseMode.BOOKING, "2026-06-21")
    add("offset_depois_3d", "depois de 3 dias", REFERENCE, DateParseMode.BOOKING, "2026-06-10")

    # --- extra coverage toward 120+ ---
    add("extra_hoje_ref", "consulta de hoje", REFERENCE, DateParseMode.REFERENCE, "2026-06-07")
    add("extra_amanha_cancel", "cancelamento amanha", REFERENCE, DateParseMode.REFERENCE, "2026-06-08")
    add("extra_prox_sab", "prox sab", REFERENCE, DateParseMode.BOOKING, "2026-06-13")
    add("extra_5f", "5f", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("extra_na_proxima_sexta", "na proxima sexta", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("extra_semana_que_vem_terca", "semana que vem terca", REFERENCE, DateParseMode.BOOKING, "2026-06-09")
    add("extra_passada_quinta_ref", "quinta passada", REFERENCE, DateParseMode.REFERENCE, "2026-06-04")
    add("extra_nesse_fds", "nesse fim de semana", WED, DateParseMode.BOOKING, "2026-06-06")
    add("extra_daqui_5d", "daqui 5 dias", REFERENCE, DateParseMode.BOOKING, "2026-06-12")
    add("extra_em_10d", "em 10 dias", REFERENCE, DateParseMode.BOOKING, "2026-06-17")
    add("extra_dia_20_jun", "dia 20 de junho", REFERENCE, DateParseMode.BOOKING, "2026-06-20")
    add("extra_dia_20_only", "dia 20", REFERENCE, DateParseMode.BOOKING, "2026-06-20")
    add("extra_iso_in_cancel", "cancelar 2026-06-12", REFERENCE, DateParseMode.REFERENCE, "2026-06-12")
    add("extra_multi_wd_three", "segunda terca ou quarta", REFERENCE, DateParseMode.BOOKING, None, clarify="multiple_weekdays")
    add("extra_essa_semana_ref", "essa semana", REFERENCE, DateParseMode.REFERENCE, None, clarify="week_hint_only")
    add("extra_depois_amanha_ref", "atraso depois de amanha", REFERENCE, DateParseMode.REFERENCE, "2026-06-09")
    add("extra_sabado_que_vem", "sabado que vem", REFERENCE, DateParseMode.BOOKING, "2026-06-13")
    add("extra_prox_quinta", "prox quinta", REFERENCE, DateParseMode.BOOKING, "2026-06-11")
    add("extra_terca_ou_quarta", "terca ou quarta", REFERENCE, DateParseMode.BOOKING, None, clarify="multiple_weekdays")
    add("extra_util_accent", "em 2 dias úteis", REFERENCE, DateParseMode.BOOKING, "2026-06-09")

    return tuple(c)


TEMPORAL_MATRIX: tuple[TemporalCase, ...] = _cases()

# Hints without resolvable ISO (routing-only signals).
HINT_ONLY_CASES: tuple[tuple[str, bool], ...] = (
    ("essa semana", True),
    ("contemporaneo", False),
    ("Onde fica o salão?", False),
    ("Quero agendar amanhã", True),
    ("R$ 10/06 no cardápio", False),
    ("de tarde", False),
    ("de manhã", False),
)

# Optional LLM-behavior tier D — rare phrasing smoke (not run in default CI).
LLM_BEHAVIOR_TEMPORAL_CASES: tuple[tuple[str, str | None], ...] = (
    ("tipo semana que vem sabe", None),
    ("sexta ou sábado tanto faz", None),
    ("quarta da outra semana", None),
)
