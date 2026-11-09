
from datetime import datetime

from flask import (
    Blueprint, render_template, request,
    redirect, url_for
)

from database.connection import get_connection

patients_bp = Blueprint(
    "patients",
    __name__,
    url_prefix="/patients"
)


def calculate_age(date_of_birth):
    if not date_of_birth:
        return None

    today = datetime.now().date()
    age = today.year - date_of_birth.year

    if (today.month, today.day) < (
        date_of_birth.month,
        date_of_birth.day
    ):
        age -= 1

    return age


@patients_bp.route("/", methods=["GET", "POST"])
def patient_list():

    message = None
    message_type = None

    status = request.args.get("status")

    if status == "updated":
        message = "Patient information updated successfully!"
        message_type = "success"
    
    elif status == "deleted":
        message = "Patient deleted successfully!"
        message_type = "success"

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        gender = request.form.get("gender", "")
        date_value = request.form.get("date_of_birth", "")
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        blood_group = request.form.get("blood_group", "")

        allowed_genders = ["Male", "Female", "Other"]

        allowed_blood_groups = [
            "A+", "A-", "B+", "B-",
            "AB+", "AB-", "O+", "O-"
        ]

        if not full_name or gender not in allowed_genders:
            message = "Please enter a valid name and gender."
            message_type = "error"

        elif blood_group and blood_group not in allowed_blood_groups:
            message = "Invalid blood group."
            message_type = "error"

        else:
            conn = None
            cursor = None

            try:
                date_of_birth = (
                    datetime.strptime(date_value, "%Y-%m-%d")
                    if date_value else None
                )

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO patients (
                        full_name, gender, date_of_birth,
                        phone, address, blood_group
                    )
                    VALUES (
                        :full_name, :gender, :date_of_birth,
                        :phone, :address, :blood_group
                    )
                """, {
                    "full_name": full_name,
                    "gender": gender,
                    "date_of_birth": date_of_birth,
                    "phone": phone or None,
                    "address": address or None,
                    "blood_group": blood_group or None
                })

                conn.commit()

                message = "Patient registered successfully!"
                message_type = "success"

            except Exception as error:
                if conn:
                    conn.rollback()

                print("PATIENT REGISTRATION ERROR:", repr(error))

                message = "Registration failed. Please try again."
                message_type = "error"

            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

    search = request.args.get("search", "").strip()

    patients = []
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT patient_id, full_name, gender,
                   date_of_birth, phone, address, blood_group
            FROM patients
        """

        params = {}

        if search:
            sql += """
                WHERE LOWER(full_name) LIKE :search_text
                   OR phone LIKE :search_text
            """

            params["search_text"] = f"%{search.lower()}%"

            if search.isdigit():
                sql += " OR patient_id = :patient_id"
                params["patient_id"] = int(search)

        sql += " ORDER BY patient_id DESC"

        cursor.execute(sql, params)

        for row in cursor.fetchall():
            patients.append({
                "patient_id": row[0],
                "full_name": row[1],
                "gender": row[2],
                "date_of_birth": row[3],
                "age": calculate_age(row[3]),
                "phone": row[4],
                "address": row[5],
                "blood_group": row[6]
            })

    except Exception as error:
        print("PATIENT LIST ERROR:", repr(error))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template(
        "patients.html",
        message=message,
        message_type=message_type,
        patients=patients,
        search=search
    )


@patients_bp.route("/edit/<int:patient_id>", methods=["GET", "POST"])
def edit_patient(patient_id):

    conn = None
    cursor = None
    patient = None
    message = None
    message_type = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT patient_id, full_name, gender,
                   date_of_birth, phone, address, blood_group
            FROM patients
            WHERE patient_id = :patient_id
        """, {"patient_id": patient_id})

        row = cursor.fetchone()

        if not row:
            return "Patient not found", 404

        patient = {
            "patient_id": row[0],
            "full_name": row[1],
            "gender": row[2],
            "date_of_birth": row[3],
            "phone": row[4],
            "address": row[5],
            "blood_group": row[6]
        }

        if request.method == "POST":

            full_name = request.form.get("full_name", "").strip()
            gender = request.form.get("gender", "")
            date_value = request.form.get("date_of_birth", "")
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()
            blood_group = request.form.get("blood_group", "")

            allowed_genders = ["Male", "Female", "Other"]
            allowed_blood_groups = [
                "A+", "A-", "B+", "B-",
                "AB+", "AB-", "O+", "O-"
            ]

            if not full_name or gender not in allowed_genders:
                message = "Please enter a valid name and gender."
                message_type = "error"

            elif blood_group and blood_group not in allowed_blood_groups:
                message = "Invalid blood group."
                message_type = "error"

            else:
                date_of_birth = (
                    datetime.strptime(date_value, "%Y-%m-%d")
                    if date_value else None
                )

                cursor.execute("""
                    UPDATE patients
                    SET full_name = :full_name,
                        gender = :gender,
                        date_of_birth = :date_of_birth,
                        phone = :phone,
                        address = :address,
                        blood_group = :blood_group
                    WHERE patient_id = :patient_id
                """, {
                    "full_name": full_name,
                    "gender": gender,
                    "date_of_birth": date_of_birth,
                    "phone": phone or None,
                    "address": address or None,
                    "blood_group": blood_group or None,
                    "patient_id": patient_id
                })

                conn.commit()

                return redirect(
                    url_for("patients.patient_list", status="updated")
                )

            patient.update({
                "full_name": full_name,
                "gender": gender,
                "date_of_birth": (
                    datetime.strptime(date_value, "%Y-%m-%d")
                    if date_value else None
                ),
                "phone": phone,
                "address": address,
                "blood_group": blood_group
            })

    except Exception as error:
        if conn:
            conn.rollback()

        print("PATIENT EDIT ERROR:", repr(error))
        message = "Unable to update patient information."
        message_type = "error"

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

        return render_template(
        "edit_patient.html",
        patient=patient,
        message=message,
        message_type=message_type
    )



@patients_bp.route("/delete/<int:patient_id>", methods=["POST"])
def delete_patient(patient_id):

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM patients
            WHERE patient_id = :patient_id
        """, {"patient_id": patient_id})

        if cursor.rowcount == 0:
            return "Patient not found", 404

        conn.commit()

        return redirect(
            url_for("patients.patient_list", status="deleted")
        )

    except Exception as error:
        if conn:
            conn.rollback()

        print("PATIENT DELETE ERROR:", repr(error))

        return (
            "Patient could not be deleted. "
            "This patient may have existing appointments.",
            409
        )

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()
