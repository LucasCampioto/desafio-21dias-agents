"""Classificação determinística por palavras-chave (PT) em domínios temáticos."""

import re

DOMAINS = frozenset(
    {"finance", "relationships", "self_worth", "journey_meta", "general"}
)

_META_PATTERNS = [
    r"\bevolu(c|ç)(a|ã)o\b",
    r"\bprogresso\b",
    r"\bjornada\b",
    r"\bcampanha\b",
    r"\brelatório\b|\brelatorio\b",
    r"\bbox\b",
]
_FINANCE_TERMS = [
    "financeir",
    "dinheiro",
    "dinheiros",
    "compra",
    "comprar",
    "dívida",
    "divida",
    "dívidas",
    "dividas",
    "invest",
    "gasto",
    "gastar",
    "salário",
    "salario",
    "orcamento",
    "orçamento",
    "impulso",
    "consumo",
    "cartão",
    "cartao",
    "extrato",
    "economia",
    "poupan",
    "prosperidade",
    "abundanci",
    "macbook",
    "iphone",
    "notebook",
    "gadget",
]

_REL_TERMS = [
    "família",
    "familia",
    "pai",
    "mãe",
    "mae",
    "mães",
    "maes",
    "filho",
    "filha",
    "parceiro",
    "parceira",
    "namorado",
    "namorada",
    "marido",
    "esposa",
    "cônjuge",
    "conjuge",
    "amigo",
    "amiga",
    "relacionamento",
    "convívio",
    "convivi",
]

_SELF_TERMS = [
    "autoestima",
    "identidade",
    "compara",
    "insegurança",
    "inseguranca",
    "culpa",
    "vergonha",
    "inútil",
    "inutil",
    "incrível",
    "incapaz",
    "valor",
    "mérito",
    "merito",
    "sou suficient",
]


def classify_topic(text: str) -> str:
    """Classifica mensagem da usuária em um único domínio (prioridade: meta → finanças → relações → auto → geral)."""
    if not text or not text.strip():
        return "general"

    t_norm = text.lower().strip()
    compact = " ".join(t_norm.split())

    def _hits_meta() -> bool:
        for pattern in _META_PATTERNS:
            if re.search(pattern, compact, re.IGNORECASE):
                return True
        phrases = ["como estou", "como anda", "como foi", "minha vida emoc"]
        return any(p in compact for p in phrases) and ("evolu" in compact or "progress" in compact)

    if _hits_meta():
        return "journey_meta"

    for term in _FINANCE_TERMS:
        if term in compact:
            return "finance"

    for term in _REL_TERMS:
        if term in compact:
            return "relationships"

    for term in _SELF_TERMS:
        if term in compact:
            return "self_worth"

    return "general"
