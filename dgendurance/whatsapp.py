"""Links do WhatsApp: abrem a conversa com a mensagem já escrita, é só tocar em enviar."""
from __future__ import annotations

from urllib.parse import quote


def link_whatsapp(telefone: str, mensagem: str) -> str:
    numero = "".join(c for c in telefone if c.isdigit())
    return f"https://wa.me/{numero}?text={quote(mensagem)}"
