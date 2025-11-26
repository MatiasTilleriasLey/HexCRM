from __future__ import annotations

from jinja2 import Environment, BaseLoader


def render_proposal_body(template_body: str, context: dict) -> str:
    """Renderiza el cuerpo de una propuesta usando Jinja2.

    Ejemplo de variables disponibles:
      - client_name
      - client_company
      - service_focus
      - validity_days
      - price
    """
    env = Environment(loader=BaseLoader(), autoescape=False)
    jinja_template = env.from_string(template_body)
    return jinja_template.render(**context)

