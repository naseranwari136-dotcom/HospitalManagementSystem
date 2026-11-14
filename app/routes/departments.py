import oracledb
from flask import Blueprint, render_template, request, redirect, url_for
from database.connection import get_connection

departments_bp = Blueprint(
    "departments", __name__, url_prefix="/departments"
)


def get_departments(cursor, search=""):
    sql = """
        SELECT d.DEPARTMENT_ID,
               d.NAME,
               d.LOCATION,
               COUNT(doc.DOCTOR_ID) AS DOCTOR_COUNT
        FROM DEPARTMENTS d
        LEFT JOIN DOCTORS doc
            ON d.DEPARTMENT_ID = doc.DEPARTMENT_ID
    """

    params = {}

    if search:
        sql += """
            WHERE LOWER(d.NAME) LIKE LOWER(:search)
               OR TO_CHAR(d.DEPARTMENT_ID) LIKE :search
        """
        params["search"] = f"%{search}%"

    sql += """
        GROUP BY d.DEPARTMENT_ID, d.NAME, d.LOCATION
        ORDER BY d.DEPARTMENT_ID DESC
    """

    cursor.execute(sql, params)
    return cursor.fetchall()


@departments_bp.route("/", methods=["GET", "POST"])
def departments_list():
    conn = None
    cursor = None

    message = None
    message_type = "success"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            location = request.form.get("location", "").strip()

            if not name:
                message = "Department name is required."
                message_type = "danger"

            else:
                try:
                    cursor.execute("""
                        INSERT INTO DEPARTMENTS (NAME, LOCATION)
                        VALUES (:name, :location)
                    """, {
                        "name": name,
                        "location": location or None
                    })

                    conn.commit()

                    return redirect(
                        url_for(
                            "departments.departments_list",
                            status="created"
                        )
                    )

                except oracledb.IntegrityError as error:
                    conn.rollback()

                    if "UQ_DEPARTMENTS_NAME" in str(error).upper():
                        message = "A department with this name already exists."
                    else:
                        message = "Department could not be registered."

                    message_type = "danger"

                except Exception as error:
                    conn.rollback()
                    print("DEPARTMENT REGISTRATION ERROR:", repr(error))
                    message = "Department registration failed."
                    message_type = "danger"

        search = request.args.get("search", "").strip()

        departments = get_departments(cursor, search)

        cursor.execute("SELECT COUNT(*) FROM DEPARTMENTS")
        total_departments = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM DOCTORS")
        total_doctors = cursor.fetchone()[0]

        status = request.args.get("status")

        if status == "created":
            message = "Department registered successfully."
        elif status == "updated":
            message = "Department updated successfully."
        elif status == "deleted":
            message = "Department deleted successfully."
        elif status == "has_doctors":
            message = "This department cannot be deleted because doctors are assigned to it."
            message_type = "danger"
        elif status == "error":
            message = "The requested operation could not be completed."
            message_type = "danger"

        return render_template(
            "departments.html",
            departments=departments,
            total_departments=total_departments,
            total_doctors=total_doctors,
            search=search,
            message=message,
            message_type=message_type
        )

    except Exception as error:
        print("DEPARTMENTS PAGE ERROR:", repr(error))

        return render_template(
            "departments.html",
            departments=[],
            total_departments=0,
            total_doctors=0,
            search=request.args.get("search", ""),
            message="Unable to load departments. Check the database connection.",
            message_type="danger"
        )

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@departments_bp.route("/edit/<int:department_id>", methods=["GET", "POST"])
def edit_department(department_id):
    conn = None
    cursor = None
    department = None
    message = None
    message_type = "danger"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DEPARTMENT_ID, NAME, LOCATION
            FROM DEPARTMENTS
            WHERE DEPARTMENT_ID = :department_id
        """, {"department_id": department_id})

        row = cursor.fetchone()

        if row is None:
            return redirect(
                url_for("departments.departments_list", status="error")
            )

        department = {
            "department_id": row[0],
            "name": row[1],
            "location": row[2] or ""
        }

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            location = request.form.get("location", "").strip()

            department["name"] = name
            department["location"] = location

            if not name:
                message = "Department name is required."

            else:
                try:
                    cursor.execute("""
                        UPDATE DEPARTMENTS
                        SET NAME = :name,
                            LOCATION = :location
                        WHERE DEPARTMENT_ID = :department_id
                    """, {
                        "name": name,
                        "location": location or None,
                        "department_id": department_id
                    })

                    if cursor.rowcount == 0:
                        conn.rollback()
                        return redirect(
                            url_for(
                                "departments.departments_list",
                                status="error"
                            )
                        )

                    conn.commit()

                    return redirect(
                        url_for(
                            "departments.departments_list",
                            status="updated"
                        )
                    )

                except oracledb.IntegrityError as error:
                    conn.rollback()

                    if "UQ_DEPARTMENTS_NAME" in str(error).upper():
                        message = "Another department already has this name."
                    else:
                        message = "Department information could not be updated."

                except Exception as error:
                    conn.rollback()
                    print("DEPARTMENT UPDATE ERROR:", repr(error))
                    message = "Unable to update department."

    except Exception as error:
        if conn:
            conn.rollback()

        print("EDIT DEPARTMENT ERROR:", repr(error))
        message = "Unable to load department information."

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template(
        "edit_department.html",
        department=department,
        message=message,
        message_type=message_type
    )


@departments_bp.route("/delete/<int:department_id>", methods=["POST"])
def delete_department(department_id):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM DOCTORS
            WHERE DEPARTMENT_ID = :department_id
        """, {"department_id": department_id})

        doctor_count = cursor.fetchone()[0]

        if doctor_count > 0:
            return redirect(
                url_for(
                    "departments.departments_list",
                    status="has_doctors"
                )
            )

        cursor.execute("""
            DELETE FROM DEPARTMENTS
            WHERE DEPARTMENT_ID = :department_id
        """, {"department_id": department_id})

        if cursor.rowcount == 0:
            return redirect(
                url_for("departments.departments_list", status="error")
            )

        conn.commit()

        return redirect(
            url_for("departments.departments_list", status="deleted")
        )

    except Exception as error:
        if conn:
            conn.rollback()

        print("DELETE DEPARTMENT ERROR:", repr(error))

        return redirect(
            url_for(
                "departments.departments_list",
                status="has_doctors"
            )
        )

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
