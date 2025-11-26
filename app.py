from __future__ import annotations

import json
import os
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    url_for,
    flash,
    session,
    make_response,
)
from sqlalchemy import inspect, text
from werkzeug.exceptions import NotFound
from werkzeug.security import check_password_hash, generate_password_hash
from weasyprint import HTML
from jinja2 import Environment, BaseLoader
from werkzeug.utils import secure_filename

from models import db, Client, Proposal, User

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
TEMPLATE_UPLOAD_DIR = BASE_DIR / "uploaded_templates"
TEMPLATE_METADATA_PATH = TEMPLATE_UPLOAD_DIR / "templates.json"


def create_app() -> Flask:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-me",
    )

    db_path = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'crm.db'}",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = db_path
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _ensure_user_name_column(db)
        _ensure_proposal_extra_columns(db)
        _drop_template_artifacts(db)
        TEMPLATE_UPLOAD_DIR.mkdir(exist_ok=True)
        
    register_routes(app)
    return app


def _ensure_user_name_column(db_obj: db) -> None:
    """Ensure the users table has the full_name column (for existing DBs)."""
    inspector = inspect(db_obj.engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("users")}
    if "full_name" not in columns:
        with db_obj.engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(120)"))


def _ensure_proposal_extra_columns(db_obj: db) -> None:
    """Add new proposal columns for richer context."""
    inspector = inspect(db_obj.engine)
    if "proposals" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("proposals")}
    alters = []
    if "objectives" not in columns:
        alters.append("ADD COLUMN objectives TEXT")
    if "scope_text" not in columns:
        alters.append("ADD COLUMN scope_text TEXT")
    if "deliverables" not in columns:
        alters.append("ADD COLUMN deliverables TEXT")
    if "tech_stack" not in columns:
        alters.append("ADD COLUMN tech_stack TEXT")
    if "work_plan" not in columns:
        alters.append("ADD COLUMN work_plan TEXT")
    if "cost_breakdown" not in columns:
        alters.append("ADD COLUMN cost_breakdown TEXT")
    if "cost_items" not in columns:
        alters.append("ADD COLUMN cost_items TEXT")
    if "validity_days" not in columns:
        alters.append("ADD COLUMN validity_days INTEGER")

    if not alters:
        return

    with db_obj.engine.begin() as conn:
        for clause in alters:
            conn.execute(text(f"ALTER TABLE proposals {clause}"))


def _drop_template_artifacts(db_obj: db) -> None:
    """Drop legacy template tables/columns no longer used."""
    inspector = inspect(db_obj.engine)
    tables = inspector.get_table_names()

    with db_obj.engine.begin() as conn:
        if "proposal_template_sections" in tables:
            conn.execute(text("DROP TABLE proposal_template_sections"))
        if "proposal_templates" in tables:
            conn.execute(text("DROP TABLE proposal_templates"))

        cols = {col["name"] for col in inspector.get_columns("proposals")}
        if "template_id" in cols:
            try:
                conn.execute(text("ALTER TABLE proposals DROP COLUMN template_id"))
            except Exception:
                pass
        if "section_overrides" in cols:
            try:
                conn.execute(text("ALTER TABLE proposals DROP COLUMN section_overrides"))
            except Exception:
                pass


def _list_uploaded_templates() -> list[dict[str, str]]:
    """Return list of saved HTML templates with labels."""
    TEMPLATE_UPLOAD_DIR.mkdir(exist_ok=True)
    metadata = _load_template_metadata()
    templates: list[dict[str, str]] = []
    for path in TEMPLATE_UPLOAD_DIR.glob("*.html"):
        templates.append(
            {
                "filename": path.name,
                "label": metadata.get(path.name) or path.stem,
            }
        )
    return sorted(templates, key=lambda t: t["label"].lower())


def _load_template_metadata() -> dict[str, str]:
    """Load template display names keyed by filename."""
    TEMPLATE_UPLOAD_DIR.mkdir(exist_ok=True)
    if not TEMPLATE_METADATA_PATH.exists():
        return {}
    try:
        return json.loads(TEMPLATE_METADATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_template_metadata(metadata: dict[str, str]) -> None:
    """Persist template display names."""
    TEMPLATE_UPLOAD_DIR.mkdir(exist_ok=True)
    TEMPLATE_METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_template_from_request() -> str:
    """Obtain the HTML template contents from the current request."""
    template_choice = request.form.get("template_choice", "upload")
    if template_choice == "upload":
        file = request.files.get("template_file")
        if not file or file.filename == "":
            raise ValueError("Debes subir un archivo HTML.")
        return file.stream.read().decode("utf-8", errors="ignore")

    selected = request.form.get("saved_template")
    if not selected:
        raise ValueError("Selecciona una plantilla guardada.")
    tpl_path = TEMPLATE_UPLOAD_DIR / selected
    if not tpl_path.exists():
        raise ValueError("Plantilla no encontrada.")
    return tpl_path.read_text(encoding="utf-8")


def _render_proposal_html(template_str: str, proposal: Proposal) -> str:
    """Render the template string with the proposal context."""
    env = Environment(loader=BaseLoader(), autoescape=False)
    jinja_template = env.from_string(template_str)
    return jinja_template.render(proposal=proposal)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if User.query.count() == 0:
            return redirect(url_for("setup"))

        user_id = session.get("user_id")
        username = session.get("user")
        user = None
        if user_id:
            user = User.query.get(user_id)
        elif username:
            user = User.query.filter_by(username=username).first()

        if not user:
            session.pop("user", None)
            session.pop("user_id", None)
            session.pop("user_name", None)
            next_url = request.path
            return redirect(url_for("login", next=next_url))
        return view(*args, **kwargs)

    return wrapped


def register_routes(app: Flask) -> None:
    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("list_clients"))

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if User.query.count() > 0:
            flash("Ya existe un usuario, inicia sesión.", "info")
            return redirect(url_for("login"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            full_name = request.form.get("full_name", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not username or not password or not full_name:
                flash("Nombre, usuario y contraseña son obligatorios.", "error")
            elif password != confirm_password:
                flash("Las contraseñas no coinciden.", "error")
            elif User.query.filter_by(username=username).first():
                flash("El usuario ya existe.", "error")
            else:
                user = User(
                    username=username,
                    full_name=full_name,
                    password_hash=generate_password_hash(password),
                )
                db.session.add(user)
                db.session.commit()
                session["user_id"] = user.id
                session["user"] = user.username
                session["user_name"] = user.full_name
                flash("Usuario inicial creado. Sesión iniciada.", "success")
                return redirect(url_for("list_clients"))

        return render_template("setup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if User.query.count() == 0:
            return redirect(url_for("setup"))

        if session.get("user"):
            return redirect(url_for("list_clients"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session["user_id"] = user.id
                session["user"] = user.username
                session["user_name"] = user.full_name or user.username
                flash("Sesión iniciada.", "success")
                next_url = request.args.get("next")
                if next_url and next_url.startswith("/"):
                    return redirect(next_url)
                return redirect(url_for("list_clients"))

            flash("Credenciales inválidas.", "error")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        session.pop("user", None)
        session.pop("user_id", None)
        session.pop("user_name", None)
        flash("Sesión cerrada.", "success")
        return redirect(url_for("login"))

    # -------- CLIENTES -------- #

    @app.route("/clients")
    @login_required
    def list_clients():
        clients = Client.query.order_by(Client.created_at.desc()).all()
        return render_template("clients_list.html", clients=clients)

    @app.route("/clients/<int:client_id>/proposals")
    @login_required
    def list_client_proposals(client_id: int):
        client = Client.query.get(client_id)
        if client is None:
            raise NotFound("Cliente no encontrado.")

        proposals = Proposal.query.filter_by(client_id=client.id).order_by(
            Proposal.created_at.desc(),
        ).all()
        return render_template(
            "client_proposals.html",
            client=client,
            proposals=proposals,
        )

    @app.route("/clients/new", methods=["GET", "POST"])
    @login_required
    def create_client():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("El nombre del cliente es obligatorio.", "error")
                return render_template("client_form.html", client=None)

            client = Client(
                name=name,
                company=request.form.get("company") or None,
                email=request.form.get("email") or None,
                phone=request.form.get("phone") or None,
                notes=request.form.get("notes") or None,
            )
            db.session.add(client)
            db.session.commit()
            flash("Cliente creado correctamente.", "success")
            return redirect(url_for("list_clients"))

        return render_template("client_form.html", client=None)

    @app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_client(client_id: int):
        client = Client.query.get(client_id)
        if client is None:
            raise NotFound("Cliente no encontrado.")

        if request.method == "POST":
            client.name = request.form.get("name", "").strip()
            client.company = request.form.get("company") or None
            client.email = request.form.get("email") or None
            client.phone = request.form.get("phone") or None
            client.notes = request.form.get("notes") or None
            db.session.commit()
            flash("Cliente actualizado.", "success")
            return redirect(url_for("list_clients"))

        return render_template("client_form.html", client=client)

    @app.route("/clients/<int:client_id>/delete", methods=["POST"])
    @login_required
    def delete_client(client_id: int):
        client = Client.query.get(client_id)
        if client is None:
            raise NotFound("Cliente no encontrado.")

        db.session.delete(client)
        db.session.commit()
        flash("Cliente eliminado.", "success")
        return redirect(url_for("list_clients"))

    # -------- PROPUESTAS -------- #

    @app.route("/clients/<int:client_id>/proposals/new", methods=["GET", "POST"])
    @login_required
    def create_proposal(client_id: int):
        client = Client.query.get(client_id)
        if client is None:
            raise NotFound("Cliente no encontrado.")

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            summary = request.form.get("summary") or None
            amount = request.form.get("amount") or None
            currency = request.form.get("currency") or "CLP"
            objectives = request.form.get("objectives", "").strip() or None
            scope_text = request.form.get("scope_text", "").strip() or None
            deliverables = request.form.get("deliverables", "").strip() or None
            tech_stack = request.form.get("tech_stack", "").strip() or None
            work_plan = request.form.get("work_plan", "").strip() or None
            cost_breakdown = request.form.get("cost_breakdown", "").strip() or None
            cost_items_json = request.form.get("cost_items_json", "").strip() or None
            validity_days_raw = request.form.get("validity_days", "").strip()
            validity_days = int(validity_days_raw) if validity_days_raw else None
            body = request.form.get("body", "").strip()

            if not body:
                flash("El cuerpo de la propuesta es obligatorio.", "error")
                return render_template(
                    "proposal_form.html",
                    client=client,
                )

            context = {
                "client_name": client.name,
                "client_company": client.company or "",
                "client_email": client.email or "",
                "service_focus": request.form.get("service_focus", ""),
                "validity_days": validity_days or "",
                "price": amount,
                "currency": currency,
                "objectives": objectives or "",
                "scope": scope_text or "",
                "deliverables": deliverables or "",
                "tech_stack": tech_stack or "",
                "work_plan": work_plan or "",
                "cost_breakdown": cost_breakdown or "",
            }
            # El cuerpo ya viene escrito por el usuario; no se auto-renderiza con plantillas
            rendered_body = body

            proposal = Proposal(
                client_id=client.id,
                title=title or "Propuesta",
                summary=summary,
                body=rendered_body,
                objectives=objectives,
                scope_text=scope_text,
                deliverables=deliverables,
                tech_stack=tech_stack,
                work_plan=work_plan,
                cost_breakdown=cost_breakdown,
                cost_items=cost_items_json,
                validity_days=validity_days,
                amount=float(amount) if amount else None,
                currency=currency,
                status="draft",
            )
            db.session.add(proposal)
            db.session.commit()
            flash("Propuesta creada en borrador.", "success")
            return redirect(url_for("view_proposal", proposal_id=proposal.id))

        return render_template(
            "proposal_form.html",
            client=client,
        )

    @app.route("/proposals/<int:proposal_id>")
    @login_required
    def view_proposal(proposal_id: int):
        proposal = Proposal.query.get(proposal_id)
        if proposal is None:
            raise NotFound("Propuesta no encontrada.")

        return render_template("proposal_detail.html", proposal=proposal)

    @app.route("/proposals/<int:proposal_id>/pdf", methods=["GET", "POST"])
    @login_required
    def download_proposal_pdf(proposal_id: int):
        proposal = Proposal.query.get(proposal_id)
        if proposal is None:
            raise NotFound("Propuesta no encontrada.")

        if request.method == "POST":
            try:
                template_str = _load_template_from_request()
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("proposal_pdf_upload.html", proposal=proposal, templates=_list_uploaded_templates())

            rendered_html = _render_proposal_html(template_str, proposal)
            pdf_bytes = HTML(string=rendered_html, base_url=str(BASE_DIR)).write_pdf()
            response = make_response(pdf_bytes)
            response.headers["Content-Type"] = "application/pdf"
            response.headers[
                "Content-Disposition"
            ] = f'attachment; filename="propuesta-{proposal.id}.pdf"'
            return response

        return render_template("proposal_pdf_upload.html", proposal=proposal, templates=_list_uploaded_templates())

    @app.route("/proposals/<int:proposal_id>/preview", methods=["POST"])
    @login_required
    def preview_proposal_template(proposal_id: int):
        proposal = Proposal.query.get(proposal_id)
        if proposal is None:
            raise NotFound("Propuesta no encontrada.")

        try:
            template_str = _load_template_from_request()
        except ValueError as exc:
            return {"error": str(exc)}, 400

        rendered_html = _render_proposal_html(template_str, proposal)
        return {"html": rendered_html}

    @app.route("/templates/upload", methods=["GET", "POST"])
    @login_required
    def proposals_upload_template():
        if request.method == "POST":
            template_name = request.form.get("template_name", "").strip()
            file = request.files.get("template_file")
            if not file or file.filename == "":
                flash("Debes subir un archivo HTML.", "error")
                return render_template("templates_upload.html", templates=_list_uploaded_templates())
            filename = secure_filename(file.filename)
            if not filename.lower().endswith((".html", ".htm")):
                flash("Solo se permiten archivos .html/.htm", "error")
                return render_template("templates_upload.html", templates=_list_uploaded_templates())
            TEMPLATE_UPLOAD_DIR.mkdir(exist_ok=True)
            base_name = secure_filename(template_name) or Path(filename).stem
            if not base_name:
                base_name = "plantilla"
            ext = Path(filename).suffix.lower() or ".html"
            if ext not in {".html", ".htm"}:
                ext = ".html"
            candidate = f"{base_name}{ext}"
            counter = 1
            while (TEMPLATE_UPLOAD_DIR / candidate).exists():
                candidate = f"{base_name}-{counter}{ext}"
                counter += 1
            filename = candidate
            path = TEMPLATE_UPLOAD_DIR / filename
            file.save(path)
            metadata = _load_template_metadata()
            metadata[filename] = template_name or Path(filename).stem
            _save_template_metadata(metadata)
            flash("Plantilla guardada.", "success")
            return redirect(url_for("proposals_upload_template"))

        return render_template("templates_upload.html", templates=_list_uploaded_templates())

    @app.route("/templates/<path:filename>/delete", methods=["POST"])
    @login_required
    def delete_template(filename: str):
        safe_name = secure_filename(filename)
        if not safe_name:
            flash("Archivo inválido.", "error")
            return redirect(url_for("proposals_upload_template"))

        tpl_path = TEMPLATE_UPLOAD_DIR / safe_name
        if not tpl_path.exists():
            flash("Plantilla no encontrada.", "error")
            return redirect(url_for("proposals_upload_template"))

        tpl_path.unlink()
        metadata = _load_template_metadata()
        metadata.pop(safe_name, None)
        _save_template_metadata(metadata)
        flash("Plantilla eliminada.", "success")
        return redirect(url_for("proposals_upload_template"))

    @app.route("/templates/<path:filename>/rename", methods=["POST"])
    @login_required
    def rename_template(filename: str):
        safe_name = secure_filename(filename)
        if not safe_name:
            flash("Archivo inválido.", "error")
            return redirect(url_for("proposals_upload_template"))

        tpl_path = TEMPLATE_UPLOAD_DIR / safe_name
        if not tpl_path.exists():
            flash("Plantilla no encontrada.", "error")
            return redirect(url_for("proposals_upload_template"))

        new_name = request.form.get("template_name", "").strip()
        if not new_name:
            flash("Ingresa un nombre para la plantilla.", "error")
            return redirect(url_for("proposals_upload_template"))

        metadata = _load_template_metadata()
        metadata[safe_name] = new_name
        _save_template_metadata(metadata)
        flash("Nombre de plantilla actualizado.", "success")
        return redirect(url_for("proposals_upload_template"))

    @app.route("/docs")
    @login_required
    def docs():
        context_vars = [
            ("proposal.title", "Título de la propuesta"),
            ("proposal.summary", "Resumen interno"),
            ("proposal.status", "Estado (draft, sent, etc.)"),
            ("proposal.amount", "Monto"),
            ("proposal.currency", "Divisa"),
            ("proposal.validity_days", "Días de validez"),
            ("proposal.body", "Cuerpo en HTML o texto"),
            ("proposal.objectives", "Objetivos (texto)"),
            ("proposal.scope_text", "Alcance (texto)"),
            ("proposal.deliverables", "Entregables"),
            ("proposal.tech_stack", "Stack tecnológico"),
            ("proposal.work_plan", "Plan de trabajo"),
            ("proposal.cost_breakdown", "Desglose económico"),
            ("proposal.client.name", "Nombre del cliente"),
            ("proposal.client.company", "Compañía"),
            ("proposal.client.email", "Correo"),
            ("proposal.client.phone", "Teléfono"),
        ]
        return render_template(
            "docs.html",
            context_vars=context_vars,
        )

    @app.route("/proposals/<int:proposal_id>/delete", methods=["POST"])
    @login_required
    def delete_proposal(proposal_id: int):
        proposal = Proposal.query.get(proposal_id)
        if proposal is None:
            raise NotFound("Propuesta no encontrada.")
        client_id = proposal.client_id
        db.session.delete(proposal)
        db.session.commit()
        flash("Propuesta eliminada.", "success")
        return redirect(url_for("list_client_proposals", client_id=client_id))

    @app.route("/proposals/<int:proposal_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_proposal(proposal_id: int):
        proposal = Proposal.query.get(proposal_id)
        if proposal is None:
            raise NotFound("Propuesta no encontrada.")

        if request.method == "POST":
            proposal.title = request.form.get("title", "").strip() or proposal.title
            proposal.summary = request.form.get("summary", "").strip() or None
            proposal.amount = float(request.form.get("amount")) if request.form.get("amount") else None
            proposal.currency = request.form.get("currency", "").strip() or proposal.currency
            validity_days_raw = request.form.get("validity_days", "").strip()
            proposal.validity_days = int(validity_days_raw) if validity_days_raw else None

            proposal.objectives = request.form.get("objectives", "").strip() or None
            proposal.scope_text = request.form.get("scope_text", "").strip() or None
            proposal.deliverables = request.form.get("deliverables", "").strip() or None
            proposal.tech_stack = request.form.get("tech_stack", "").strip() or None
            proposal.work_plan = request.form.get("work_plan", "").strip() or None
            proposal.cost_breakdown = request.form.get("cost_breakdown", "").strip() or None
            proposal.cost_items = request.form.get("cost_items_json", "").strip() or None
            proposal.body = request.form.get("body", "").strip() or proposal.body

            db.session.commit()
            flash("Propuesta actualizada.", "success")
            return redirect(url_for("view_proposal", proposal_id=proposal.id))

        return render_template(
            "proposal_edit.html",
            proposal=proposal,
        )

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
