from flask import Blueprint, render_template, request, redirect, url_for
from database.connection import get_connection

doctors_bp = Blueprint("doctors", __name__, url_prefix="/doctors")


def get_departments(cursor):
    cursor.execute("""
        SELECT DEPARTMENT_ID, NAME
        FROM DEPARTMENTS
        ORDER BY NAME
    """)
    return cursor.fetchall()


@doctors_bp.route("/", methods=["GET", "POST"])
def doctors_list():
    conn = None
    cursor = None
    message = None
    message_type = "success"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            specialization = request.form.get("specialization", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            department_id = request.form.get("department_id", "").strip()

            if not full_name or not department_id:
                message = "Full name and department are required."
                message_type = "danger"
            else:
                cursor.execute("""
                    INSERT INTO DOCTORS
                    (FULL_NAME, SPECIALIZATION, PHONE, EMAIL, DEPARTMENT_ID)
                    VALUES (:full_name, :specialization, :phone, :email, :department_id)
                """, {
                    "full_name": full_name,
                    "specialization": specialization or None,
                    "phone": phone or None,
                    "email": email or None,
                    "department_id": int(department_id)
                })

                conn.commit()
                return redirect(url_for("doctors.doctors_list", status="created"))

        search = request.args.get("search", "").strip()

        if search:
            cursor.execute("""
                SELECT d.DOCTOR_ID, d.FULL_NAME, d.SPECIALIZATION,
                       d.PHONE, d.EMAIL, dep.NAME
                FROM DOCTORS d
                JOIN DEPARTMENTS dep
                  ON d.DEPARTMENT_ID = dep.DEPARTMENT_ID
                WHERE LOWER(d.FULL_NAME) LIKE LOWER(:search)
                   OR LOWER(d.SPECIALIZATION) LIKE LOWER(:search)
                   OR d.PHONE LIKE :search
                   OR TO_CHAR(d.DOCTOR_ID) LIKE :search
                ORDER BY d.DOCTOR_ID DESC
            """, {"search": f"%{search}%"})
        else:
            cursor.execute("""
                SELECT d.DOCTOR_ID, d.FULL_NAME, d.SPECIALIZATION,
                       d.PHONE, d.EMAIL, dep.NAME
                FROM DOCTORS d
                JOIN DEPARTMENTS dep
                  ON d.DEPARTMENT_ID = dep.DEPARTMENT_ID
                ORDER BY d.DOCTOR_ID DESC
            """)

        doctors = cursor.fetchall()
        departments = get_departments(cursor)

        cursor.execute("SELECT COUNT(*) FROM DOCTORS")
        total_doctors = cursor.fetchone()[0]

        status = request.args.get("status")
        if status == "created":
            message = "Doctor registered successfully."
        elif status == "updated":
            message = "Doctor information updated successfully."
        elif status == "deleted":
            message = "Doctor deleted successfully."
        elif status == "error":
            message = "Operation failed. Please try again."
            message_type = "danger"

        return render_template(
            "doctors.html",
            doctors=doctors,
            departments=departments,
            total_doctors=total_doctors,
            search=search,
            message=message,
            message_type=message_type
        )

    except Exception as e:
        if conn:
            conn.rollback()
        print("Doctors Error:", e)
        return render_template(
            "doctors.html",
            doctors=[],
            departments=[],
            total_doctors=0,
            search=request.args.get("search", ""),
            message="Database error: " + str(e),
            message_type="danger"
        )

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@doctors_bp.route("/edit/<int:doctor_id>", methods=["GET", "POST"])
def edit_doctor(doctor_id):
    conn = None
    cursor = None
    doctor = None
    departments = []
    message = None
    message_type = "danger"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        departments = get_departments(cursor)

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            specialization = request.form.get("specialization", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            department_id = request.form.get("department_id", "").strip()

            if not full_name or not department_id:
                message = "Full name and department are required."
            else:
                cursor.execute("""
                    UPDATE DOCTORS
                    SET FULL_NAME = :full_name,
                        SPECIALIZATION = :specialization,
                        PHONE = :phone,
                        EMAIL = :email,
                        DEPARTMENT_ID = :department_id
                    WHERE DOCTOR_ID = :doctor_id
                """, {
                    "full_name": full_name,
                    "specialization": specialization or None,
                    "phone": phone or None,
                    "email": email or None,
                    "department_id": int(department_id),
                    "doctor_id": doctor_id
                })

                if cursor.rowcount == 0:
                    message = "Doctor not found."
                else:
                    conn.commit()
                    return redirect(url_for("doctors.doctors_list", status="updated"))

        cursor.execute("""
            SELECT DOCTOR_ID, FULL_NAME, SPECIALIZATION,
                   PHONE, EMAIL, DEPARTMENT_ID
            FROM DOCTORS
            WHERE DOCTOR_ID = :doctor_id
        """, {"doctor_id": doctor_id})

        doctor = cursor.fetchone()

        if doctor is None:
            return redirect(url_for("doctors.doctors_list", status="error"))

    except Exception as e:
        if conn:
            conn.rollback()
        print("Edit Doctor Error:", e)
        message = "Database error: " + str(e)

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template(
        "edit_doctor.html",
        doctor=doctor,
        departments=departments,
        message=message,
        message_type=message_type
    )


@doctors_bp.route("/delete/<int:doctor_id>", methods=["POST"])
def delete_doctor(doctor_id):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM DOCTORS
            WHERE DOCTOR_ID = :doctor_id
        """, {"doctor_id": doctor_id})

        if cursor.rowcount == 0:
            return redirect(url_for("doctors.doctors_list", status="error"))

        conn.commit()
        return redirect(url_for("doctors.doctors_list", status="deleted"))

    except Exception as e:
        if conn:
            conn.rollback()
        print("Delete Doctor Error:", e)
        return redirect(url_for("doctors.doctors_list", status="error"))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
