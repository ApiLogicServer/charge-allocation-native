from flask import Flask, jsonify, request, render_template, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///allocation.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    gl_accounts = db.relationship("GLAccount", back_populates="department", cascade="all, delete-orphan")
    charge_definitions = db.relationship("DeptChargeDefinition", back_populates="department", cascade="all, delete-orphan")
    funding_lines = db.relationship("ProjectFundingLine", back_populates="department")

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class GLAccount(db.Model):
    __tablename__ = "gl_accounts"
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    account_number = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))

    department = db.relationship("Department", back_populates="gl_accounts")
    charge_def_lines = db.relationship("DeptChargeDefLine", back_populates="gl_account")

    def to_dict(self):
        return {
            "id": self.id,
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "account_number": self.account_number,
            "description": self.description,
        }


class DeptChargeDefinition(db.Model):
    __tablename__ = "dept_charge_definitions"
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    total_percent = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=False)

    department = db.relationship("Department", back_populates="charge_definitions")
    lines = db.relationship("DeptChargeDefLine", back_populates="definition", cascade="all, delete-orphan")
    funding_lines = db.relationship("ProjectFundingLine", back_populates="charge_definition")

    def recalculate(self):
        self.total_percent = sum(l.percent for l in self.lines)
        self.is_active = abs(self.total_percent - 100.0) < 0.0001

    def to_dict(self):
        return {
            "id": self.id,
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "name": self.name,
            "total_percent": self.total_percent,
            "is_active": self.is_active,
        }


class DeptChargeDefLine(db.Model):
    __tablename__ = "dept_charge_def_lines"
    id = db.Column(db.Integer, primary_key=True)
    definition_id = db.Column(db.Integer, db.ForeignKey("dept_charge_definitions.id"), nullable=False)
    gl_account_id = db.Column(db.Integer, db.ForeignKey("gl_accounts.id"), nullable=False)
    percent = db.Column(db.Float, nullable=False)

    definition = db.relationship("DeptChargeDefinition", back_populates="lines")
    gl_account = db.relationship("GLAccount", back_populates="charge_def_lines")

    def to_dict(self):
        return {
            "id": self.id,
            "definition_id": self.definition_id,
            "gl_account_id": self.gl_account_id,
            "gl_account_number": self.gl_account.account_number if self.gl_account else None,
            "percent": self.percent,
        }


class ProjectFundingDefinition(db.Model):
    __tablename__ = "project_funding_definitions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    total_percent = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=False)

    lines = db.relationship("ProjectFundingLine", back_populates="funding_definition", cascade="all, delete-orphan")
    projects = db.relationship("Project", back_populates="funding_definition")

    def recalculate(self):
        self.total_percent = sum(l.percent for l in self.lines)
        self.is_active = abs(self.total_percent - 100.0) < 0.0001

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "total_percent": self.total_percent,
            "is_active": self.is_active,
        }


class ProjectFundingLine(db.Model):
    __tablename__ = "project_funding_lines"
    id = db.Column(db.Integer, primary_key=True)
    funding_definition_id = db.Column(db.Integer, db.ForeignKey("project_funding_definitions.id"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    charge_definition_id = db.Column(db.Integer, db.ForeignKey("dept_charge_definitions.id"), nullable=False)
    percent = db.Column(db.Float, nullable=False)

    funding_definition = db.relationship("ProjectFundingDefinition", back_populates="lines")
    department = db.relationship("Department", back_populates="funding_lines")
    charge_definition = db.relationship("DeptChargeDefinition", back_populates="funding_lines")

    def to_dict(self):
        return {
            "id": self.id,
            "funding_definition_id": self.funding_definition_id,
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "charge_definition_id": self.charge_definition_id,
            "charge_definition_name": self.charge_definition.name if self.charge_definition else None,
            "percent": self.percent,
        }


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    funding_definition_id = db.Column(db.Integer, db.ForeignKey("project_funding_definitions.id"), nullable=True)

    funding_definition = db.relationship("ProjectFundingDefinition", back_populates="projects")
    charges = db.relationship("Charge", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "funding_definition_id": self.funding_definition_id,
            "funding_definition_name": self.funding_definition.name if self.funding_definition else None,
            "funding_definition_active": self.funding_definition.is_active if self.funding_definition else False,
        }


class Charge(db.Model):
    __tablename__ = "charges"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    description = db.Column(db.String(200))
    amount = db.Column(db.Float, nullable=False)

    project = db.relationship("Project", back_populates="charges")
    dept_allocations = db.relationship("ChargeDeptAllocation", back_populates="charge", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "description": self.description,
            "amount": self.amount,
        }


class ChargeDeptAllocation(db.Model):
    __tablename__ = "charge_dept_allocations"
    id = db.Column(db.Integer, primary_key=True)
    charge_id = db.Column(db.Integer, db.ForeignKey("charges.id"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    charge_definition_id = db.Column(db.Integer, db.ForeignKey("dept_charge_definitions.id"), nullable=False)
    percent = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)

    charge = db.relationship("Charge", back_populates="dept_allocations")
    department = db.relationship("Department")
    charge_definition = db.relationship("DeptChargeDefinition")
    gl_allocations = db.relationship("ChargeGLAllocation", back_populates="dept_allocation", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "charge_id": self.charge_id,
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "charge_definition_id": self.charge_definition_id,
            "percent": self.percent,
            "amount": self.amount,
        }


class ChargeGLAllocation(db.Model):
    __tablename__ = "charge_gl_allocations"
    id = db.Column(db.Integer, primary_key=True)
    dept_allocation_id = db.Column(db.Integer, db.ForeignKey("charge_dept_allocations.id"), nullable=False)
    gl_account_id = db.Column(db.Integer, db.ForeignKey("gl_accounts.id"), nullable=False)
    percent = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)

    dept_allocation = db.relationship("ChargeDeptAllocation", back_populates="gl_allocations")
    gl_account = db.relationship("GLAccount")

    def to_dict(self):
        return {
            "id": self.id,
            "dept_allocation_id": self.dept_allocation_id,
            "gl_account_id": self.gl_account_id,
            "gl_account_number": self.gl_account.account_number if self.gl_account else None,
            "gl_account_description": self.gl_account.description if self.gl_account else None,
            "percent": self.percent,
            "amount": self.amount,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allocate_charge(charge):
    """Cascade-allocate a charge across departments then GL accounts."""
    project = charge.project
    fd = project.funding_definition
    if not fd or not fd.is_active:
        abort(400, "Project's Funding Definition is not active (does not total 100%).")

    for fl in fd.lines:
        dept_amount = round(charge.amount * fl.percent / 100.0, 4)
        dept_alloc = ChargeDeptAllocation(
            charge=charge,
            department_id=fl.department_id,
            charge_definition_id=fl.charge_definition_id,
            percent=fl.percent,
            amount=dept_amount,
        )
        db.session.add(dept_alloc)
        db.session.flush()  # get dept_alloc.id

        cd = fl.charge_definition
        for cdl in cd.lines:
            gl_amount = round(dept_amount * cdl.percent / 100.0, 4)
            gl_alloc = ChargeGLAllocation(
                dept_allocation=dept_alloc,
                gl_account_id=cdl.gl_account_id,
                percent=cdl.percent,
                amount=gl_amount,
            )
            db.session.add(gl_alloc)


# ---------------------------------------------------------------------------
# Routes — UI
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API — Departments
# ---------------------------------------------------------------------------

@app.route("/api/departments", methods=["GET"])
def list_departments(): # TODO: pagination, filtering, etc. for all list endpoints
    return jsonify([d.to_dict() for d in Department.query.order_by(Department.name).all()])

@app.route("/api/departments", methods=["POST"])
def create_department():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name is required")
    dept = Department(name=name)
    db.session.add(dept)
    db.session.commit()
    return jsonify(dept.to_dict()), 201

@app.route("/api/departments/<int:dept_id>", methods=["GET"])
def get_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    return jsonify(dept.to_dict())

@app.route("/api/departments/<int:dept_id>", methods=["PUT"])
def update_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name is required")
    dept.name = name
    db.session.commit()
    return jsonify(dept.to_dict())

@app.route("/api/departments/<int:dept_id>", methods=["DELETE"])
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API — GL Accounts
# ---------------------------------------------------------------------------

@app.route("/api/gl_accounts", methods=["GET"])
def list_gl_accounts(): # TODO page transitions, master detail
    dept_id = request.args.get("department_id", type=int)
    q = GLAccount.query
    if dept_id:
        q = q.filter_by(department_id=dept_id)
    return jsonify([a.to_dict() for a in q.order_by(GLAccount.account_number).all()])

@app.route("/api/gl_accounts", methods=["POST"])
def create_gl_account():
    data = request.get_json(force=True)
    dept_id = data.get("department_id")
    acct = (data.get("account_number") or "").strip()
    if not dept_id or not acct:
        abort(400, "department_id and account_number are required")
    Department.query.get_or_404(dept_id)
    gl = GLAccount(department_id=dept_id, account_number=acct, description=data.get("description", ""))
    db.session.add(gl)
    db.session.commit()
    return jsonify(gl.to_dict()), 201

@app.route("/api/gl_accounts/<int:gl_id>", methods=["GET"])
def get_gl_account(gl_id):
    return jsonify(GLAccount.query.get_or_404(gl_id).to_dict())

@app.route("/api/gl_accounts/<int:gl_id>", methods=["PUT"])
def update_gl_account(gl_id):
    gl = GLAccount.query.get_or_404(gl_id)
    data = request.get_json(force=True)
    acct = (data.get("account_number") or "").strip()
    if not acct:
        abort(400, "account_number is required")
    gl.account_number = acct
    gl.description = data.get("description", gl.description)
    db.session.commit()
    return jsonify(gl.to_dict())

@app.route("/api/gl_accounts/<int:gl_id>", methods=["DELETE"])
def delete_gl_account(gl_id):
    gl = GLAccount.query.get_or_404(gl_id)
    db.session.delete(gl)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API — Dept Charge Definitions
# ---------------------------------------------------------------------------

@app.route("/api/dept_charge_definitions", methods=["GET"])
def list_dept_charge_definitions():
    dept_id = request.args.get("department_id", type=int)
    q = DeptChargeDefinition.query
    if dept_id:
        q = q.filter_by(department_id=dept_id)
    return jsonify([d.to_dict() for d in q.order_by(DeptChargeDefinition.name).all()])

@app.route("/api/dept_charge_definitions", methods=["POST"])
def create_dept_charge_definition():
    data = request.get_json(force=True)
    dept_id = data.get("department_id")
    name = (data.get("name") or "").strip()
    if not dept_id or not name:
        abort(400, "department_id and name are required")
    Department.query.get_or_404(dept_id)
    cd = DeptChargeDefinition(department_id=dept_id, name=name)
    db.session.add(cd)
    db.session.commit()
    return jsonify(cd.to_dict()), 201

@app.route("/api/dept_charge_definitions/<int:cd_id>", methods=["GET"])
def get_dept_charge_definition(cd_id):
    return jsonify(DeptChargeDefinition.query.get_or_404(cd_id).to_dict())

@app.route("/api/dept_charge_definitions/<int:cd_id>", methods=["PUT"])
def update_dept_charge_definition(cd_id):
    cd = DeptChargeDefinition.query.get_or_404(cd_id)
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name is required")
    cd.name = name
    db.session.commit()
    return jsonify(cd.to_dict())

@app.route("/api/dept_charge_definitions/<int:cd_id>", methods=["DELETE"])
def delete_dept_charge_definition(cd_id):
    cd = DeptChargeDefinition.query.get_or_404(cd_id)
    db.session.delete(cd)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API — Dept Charge Definition Lines
# ---------------------------------------------------------------------------

@app.route("/api/dept_charge_definitions/<int:cd_id>/lines", methods=["GET"])
def list_cd_lines(cd_id):
    DeptChargeDefinition.query.get_or_404(cd_id)
    lines = DeptChargeDefLine.query.filter_by(definition_id=cd_id).all()
    return jsonify([l.to_dict() for l in lines])

@app.route("/api/dept_charge_definitions/<int:cd_id>/lines", methods=["POST"])
def create_cd_line(cd_id):
    cd = DeptChargeDefinition.query.get_or_404(cd_id)
    data = request.get_json(force=True)
    gl_id = data.get("gl_account_id")
    pct = data.get("percent")
    if gl_id is None or pct is None:
        abort(400, "gl_account_id and percent are required")
    gl = GLAccount.query.get_or_404(gl_id)
    if gl.department_id != cd.department_id:
        abort(400, "GL Account does not belong to the same department as the Charge Definition")
    line = DeptChargeDefLine(definition_id=cd_id, gl_account_id=gl_id, percent=float(pct))
    db.session.add(line)
    db.session.flush()
    cd.recalculate()
    db.session.commit()
    return jsonify(line.to_dict()), 201

@app.route("/api/dept_charge_def_lines/<int:line_id>", methods=["PUT"])
def update_cd_line(line_id):
    line = DeptChargeDefLine.query.get_or_404(line_id)
    data = request.get_json(force=True)
    if "percent" in data:
        line.percent = float(data["percent"])
    if "gl_account_id" in data:
        gl = GLAccount.query.get_or_404(data["gl_account_id"])
        if gl.department_id != line.definition.department_id:
            abort(400, "GL Account does not belong to the same department as the Charge Definition")
        line.gl_account_id = data["gl_account_id"]
    line.definition.recalculate()
    db.session.commit()
    return jsonify(line.to_dict())

@app.route("/api/dept_charge_def_lines/<int:line_id>", methods=["DELETE"])
def delete_cd_line(line_id):
    line = DeptChargeDefLine.query.get_or_404(line_id)
    cd = line.definition
    db.session.delete(line)
    db.session.flush()
    cd.recalculate()
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API — Project Funding Definitions
# ---------------------------------------------------------------------------

@app.route("/api/project_funding_definitions", methods=["GET"])
def list_project_funding_definitions():
    return jsonify([d.to_dict() for d in ProjectFundingDefinition.query.order_by(ProjectFundingDefinition.name).all()])

@app.route("/api/project_funding_definitions", methods=["POST"])
def create_project_funding_definition():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name is required")
    pfd = ProjectFundingDefinition(name=name)
    db.session.add(pfd)
    db.session.commit()
    return jsonify(pfd.to_dict()), 201

@app.route("/api/project_funding_definitions/<int:pfd_id>", methods=["GET"])
def get_project_funding_definition(pfd_id):
    return jsonify(ProjectFundingDefinition.query.get_or_404(pfd_id).to_dict())

@app.route("/api/project_funding_definitions/<int:pfd_id>", methods=["PUT"])
def update_project_funding_definition(pfd_id):
    pfd = ProjectFundingDefinition.query.get_or_404(pfd_id)
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name is required")
    pfd.name = name
    db.session.commit()
    return jsonify(pfd.to_dict())

@app.route("/api/project_funding_definitions/<int:pfd_id>", methods=["DELETE"])
def delete_project_funding_definition(pfd_id):
    pfd = ProjectFundingDefinition.query.get_or_404(pfd_id)
    db.session.delete(pfd)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API — Project Funding Lines
# ---------------------------------------------------------------------------

@app.route("/api/project_funding_definitions/<int:pfd_id>/lines", methods=["GET"])
def list_pfd_lines(pfd_id):
    ProjectFundingDefinition.query.get_or_404(pfd_id)
    lines = ProjectFundingLine.query.filter_by(funding_definition_id=pfd_id).all()
    return jsonify([l.to_dict() for l in lines])

@app.route("/api/project_funding_definitions/<int:pfd_id>/lines", methods=["POST"])
def create_pfd_line(pfd_id):
    pfd = ProjectFundingDefinition.query.get_or_404(pfd_id)
    data = request.get_json(force=True)
    dept_id = data.get("department_id")
    cd_id = data.get("charge_definition_id")
    pct = data.get("percent")
    if dept_id is None or cd_id is None or pct is None:
        abort(400, "department_id, charge_definition_id, and percent are required")
    dept = Department.query.get_or_404(dept_id)
    cd = DeptChargeDefinition.query.get_or_404(cd_id)
    if cd.department_id != dept.id:
        abort(400, "Charge Definition does not belong to the specified Department")
    line = ProjectFundingLine(
        funding_definition_id=pfd_id,
        department_id=dept_id,
        charge_definition_id=cd_id,
        percent=float(pct),
    )
    db.session.add(line)
    db.session.flush()
    pfd.recalculate()
    db.session.commit()
    return jsonify(line.to_dict()), 201

@app.route("/api/project_funding_lines/<int:line_id>", methods=["PUT"])
def update_pfd_line(line_id):
    line = ProjectFundingLine.query.get_or_404(line_id)
    data = request.get_json(force=True)
    if "percent" in data:
        line.percent = float(data["percent"])
    if "department_id" in data:
        line.department_id = data["department_id"]
    if "charge_definition_id" in data:
        cd = DeptChargeDefinition.query.get_or_404(data["charge_definition_id"])
        if cd.department_id != line.department_id:
            abort(400, "Charge Definition does not belong to the Department")
        line.charge_definition_id = data["charge_definition_id"]
    line.funding_definition.recalculate()
    db.session.commit()
    return jsonify(line.to_dict())

@app.route("/api/project_funding_lines/<int:line_id>", methods=["DELETE"])
def delete_pfd_line(line_id):
    line = ProjectFundingLine.query.get_or_404(line_id)
    pfd = line.funding_definition
    db.session.delete(line)
    db.session.flush()
    pfd.recalculate()
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API — Projects
# ---------------------------------------------------------------------------

@app.route("/api/projects", methods=["GET"])
def list_projects():
    return jsonify([p.to_dict() for p in Project.query.order_by(Project.name).all()])

@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name is required")
    pfd_id = data.get("funding_definition_id")
    if pfd_id:
        ProjectFundingDefinition.query.get_or_404(pfd_id)
    proj = Project(name=name, funding_definition_id=pfd_id)
    db.session.add(proj)
    db.session.commit()
    return jsonify(proj.to_dict()), 201

@app.route("/api/projects/<int:proj_id>", methods=["GET"])
def get_project(proj_id):
    return jsonify(Project.query.get_or_404(proj_id).to_dict())

@app.route("/api/projects/<int:proj_id>", methods=["PUT"])
def update_project(proj_id):
    proj = Project.query.get_or_404(proj_id)
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name is required")
    proj.name = name
    pfd_id = data.get("funding_definition_id")
    if pfd_id:
        ProjectFundingDefinition.query.get_or_404(pfd_id)
    proj.funding_definition_id = pfd_id
    db.session.commit()
    return jsonify(proj.to_dict())

@app.route("/api/projects/<int:proj_id>", methods=["DELETE"])
def delete_project(proj_id):
    proj = Project.query.get_or_404(proj_id)
    db.session.delete(proj)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API — Charges
# ---------------------------------------------------------------------------

@app.route("/api/charges", methods=["GET"])
def list_charges():
    proj_id = request.args.get("project_id", type=int)
    q = Charge.query
    if proj_id:
        q = q.filter_by(project_id=proj_id)
    return jsonify([c.to_dict() for c in q.order_by(Charge.id).all()])

@app.route("/api/charges", methods=["POST"])
def create_charge():
    data = request.get_json(force=True)
    proj_id = data.get("project_id")
    amount = data.get("amount")
    if proj_id is None or amount is None:
        abort(400, "project_id and amount are required")
    proj = Project.query.get_or_404(proj_id)
    if not proj.funding_definition or not proj.funding_definition.is_active:
        abort(400, "Cannot post charge: Project's Funding Definition is not active (must total 100%).")
    charge = Charge(project_id=proj_id, description=data.get("description", ""), amount=float(amount))
    db.session.add(charge)
    db.session.flush()
    allocate_charge(charge)
    db.session.commit()
    return jsonify(charge.to_dict()), 201

@app.route("/api/charges/<int:charge_id>", methods=["GET"])
def get_charge(charge_id):
    return jsonify(Charge.query.get_or_404(charge_id).to_dict())

@app.route("/api/charges/<int:charge_id>", methods=["DELETE"])
def delete_charge(charge_id):
    charge = Charge.query.get_or_404(charge_id)
    db.session.delete(charge)
    db.session.commit()
    return "", 204

@app.route("/api/charges/<int:charge_id>/allocations", methods=["GET"])
def get_charge_allocations(charge_id):
    Charge.query.get_or_404(charge_id)
    dept_allocs = ChargeDeptAllocation.query.filter_by(charge_id=charge_id).all()
    result = []
    for da in dept_allocs:
        d = da.to_dict()
        d["gl_allocations"] = [g.to_dict() for g in da.gl_allocations]
        result.append(d)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Init & run
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
