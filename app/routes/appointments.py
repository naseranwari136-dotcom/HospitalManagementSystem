
from datetime import datetime

import oracledb

from flask import Blueprint, render_template, request, redirect, url_for
from database.connection import get_connection


appointments_bp = Blueprint(
    "appointments",
    __name__,
    url_prefix="/appointments"
)

ALLOWED_STATUSES = ["Scheduled", "Completed", "Cancelled"]


def get_form_data(cursor):
    cursor.execute("""
        SELECT PATIENT_ID, FULL_NAME
        FROM PATIENTS
        ORDER BY FULL_NAME
    """)
    patients = cursor.fetchall()

    cursor.execute("""
        SELECT DOCTOR_ID, FULL_NAME
        FROM DOCTORS
        ORDER BY FULL_NAME
    """)
    doctors = cursor.fetchall()

    return patients, doctors


def format_time_for_input(value):
    if not value:
        return ""

    for time_format in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(
                value.strip(), time_format
            ).strftime("%H:%M")
        except ValueError:
            continue

    return ""


def get_appointment_time(value):
    return datetime.strptime(value, "%H:%M").strftime("%H:%M")


def normalize_time(value):
    if not value:
        return ""

    for time_format in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(
                value.strip(), time_format
            ).strftime("%H:%M")
        except ValueError:
            continue

    return value.strip()


def check_appointment_conflict(
    cursor,
    patient_id,
    doctor_id,
    appointment_date,
    appointment_time,
    exclude_appointment_id=None
):
    sql = """
        SELECT
            PATIENT_ID,
            DOCTOR_ID,
            APPOINTMENT_TIME
        FROM APPOINTMENTS
        WHERE TRUNC(APPOINTMENT_DATE) = TRUNC(:appointment_date)
          AND STATUS = 'Scheduled'
    """

    params = {
        "appointment_date": appointment_date
    }

    if exclude_appointment_id is not None:
        sql += " AND APPOINTMENT_ID <> :exclude_id"
        params["exclude_id"] = exclude_appointment_id

    cursor.execute(sql, params)

    selected_time = normalize_time(appointment_time)

    for row in cursor.fetchall():
        existing_patient_id = row[0]
        existing_doctor_id = row[1]
        existing_time = normalize_time(row[2])

        if existing_time != selected_time:
            continue

        if existing_doctor_id == doctor_id:
            return (
                "This doctor already has a scheduled "
                "appointment at this date and time."
            )

        if existing_patient_id == patient_id:
            return (
                "This patient already has a scheduled "
                "appointment at this date and time."
            )

    return None


def get_database_conflict_message(error):
    error_text = str(error)

    if "UX_APPT_DOCTOR_SLOT" in error_text:
        return (
            "This doctor already has a scheduled "
            "appointment at this date and time."
        )

    if "UX_APPT_PATIENT_SLOT" in error_text:
        return (
            "This patient already has a scheduled "
            "appointment at this date and time."
        )

    return "Database rejected this appointment. Please check the information."


@appointments_bp.route("/", methods=["GET", "POST"])
def appointment_list():
    conn = None
    cursor = None
    message = None
    message_type = "success"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        patients, doctors = get_form_data(cursor)

        if request.method == "POST":
            patient_id = request.form.get("patient_id", "").strip()
            doctor_id = request.form.get("doctor_id", "").strip()
            date_value = request.form.get("appointment_date", "").strip()
            time_value = request.form.get("appointment_time", "").strip()
            appointment_status = request.form.get(
                "status", "Scheduled"
            ).strip()

            if not all([
                patient_id,
                doctor_id,
                date_value,
                time_value
            ]):
                message = "All appointment fields are required."
                message_type = "danger"

            elif appointment_status not in ALLOWED_STATUSES:
                message = "Invalid appointment status."
                message_type = "danger"

            else:
                try:
                    patient_id = int(patient_id)
                    doctor_id = int(doctor_id)

                    appointment_date = datetime.strptime(
                        date_value, "%Y-%m-%d"
                    )

                    appointment_time = get_appointment_time(time_value)

                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM PATIENTS
                        WHERE PATIENT_ID = :patient_id
                    """, {"patient_id": patient_id})

                    patient_exists = cursor.fetchone()[0]

                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM DOCTORS
                        WHERE DOCTOR_ID = :doctor_id
                    """, {"doctor_id": doctor_id})

                    doctor_exists = cursor.fetchone()[0]

                    if not patient_exists or not doctor_exists:
                        message = (
                            "Selected patient or doctor does not exist."
                        )
                        message_type = "danger"

                    else:
                        conflict = None

                        if appointment_status == "Scheduled":
                            conflict = check_appointment_conflict(
                                cursor,
                                patient_id,
                                doctor_id,
                                appointment_date,
                                appointment_time
                            )

                        if conflict:
                            message = conflict
                            message_type = "danger"

                        else:
                            try:
                                cursor.execute("""
                                    INSERT INTO APPOINTMENTS (
                                        PATIENT_ID,
                                        DOCTOR_ID,
                                        APPOINTMENT_DATE,
                                        APPOINTMENT_TIME,
                                        STATUS
                                    )
                                    VALUES (
                                        :patient_id,
                                        :doctor_id,
                                        :appointment_date,
                                        :appointment_time,
                                        :status
                                    )
                                """, {
                                    "patient_id": patient_id,
                                    "doctor_id": doctor_id,
                                    "appointment_date": appointment_date,
                                    "appointment_time": appointment_time,
                                    "status": appointment_status
                                })

                                conn.commit()

                                return redirect(
                                    url_for(
                                        "appointments.appointment_list",
                                        status="created"
                                    )
                                )

                            except oracledb.IntegrityError as error:
                                conn.rollback()
                                message = get_database_conflict_message(error)
                                message_type = "danger"

                except ValueError:
                    message = "Invalid ID, date or time format."
                    message_type = "danger"

        search = request.args.get("search", "").strip()

        sql = """
            SELECT
                a.APPOINTMENT_ID,
                p.FULL_NAME,
                d.FULL_NAME,
                a.APPOINTMENT_DATE,
                a.APPOINTMENT_TIME,
                a.STATUS
            FROM APPOINTMENTS a
            JOIN PATIENTS p
                ON a.PATIENT_ID = p.PATIENT_ID
            JOIN DOCTORS d
                ON a.DOCTOR_ID = d.DOCTOR_ID
        """

        params = {}

        if search:
            sql += """
                WHERE LOWER(p.FULL_NAME) LIKE LOWER(:search)
                   OR LOWER(d.FULL_NAME) LIKE LOWER(:search)
                   OR LOWER(a.STATUS) LIKE LOWER(:search)
                   OR TO_CHAR(a.APPOINTMENT_ID) LIKE :search
            """
            params["search"] = f"%{search}%"

        sql += """
            ORDER BY a.APPOINTMENT_DATE DESC,
                     a.APPOINTMENT_ID DESC
        """

        cursor.execute(sql, params)
        appointments = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM APPOINTMENTS")
        total_appointments = cursor.fetchone()[0]

        status = request.args.get("status")

        if status == "created":
            message = "Appointment registered successfully."
        elif status == "updated":
            message = "Appointment updated successfully."
        elif status == "deleted":
            message = "Appointment deleted successfully."
        elif status == "error":
            message = "Operation failed. Please try again."
            message_type = "danger"

        return render_template(
            "appointments.html",
            appointments=appointments,
            patients=patients,
            doctors=doctors,
            total_appointments=total_appointments,
            search=search,
            message=message,
            message_type=message_type
        )

    except Exception as error:
        if conn:
            conn.rollback()

        print("Appointments Error:", repr(error))

        return render_template(
            "appointments.html",
            appointments=[],
            patients=[],
            doctors=[],
            total_appointments=0,
            search=request.args.get("search", ""),
            message="Database error. Please check the application logs.",
            message_type="danger"
        )

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@appointments_bp.route(
    "/edit/<int:appointment_id>",
    methods=["GET", "POST"]
)
def edit_appointment(appointment_id):
    conn = None
    cursor = None

    patients = []
    doctors = []
    appointment = None

    message = None
    message_type = "danger"

    form_values = {}

    try:
        conn = get_connection()
        cursor = conn.cursor()

        patients, doctors = get_form_data(cursor)

        cursor.execute("""
            SELECT
                APPOINTMENT_ID,
                PATIENT_ID,
                DOCTOR_ID,
                APPOINTMENT_DATE,
                APPOINTMENT_TIME,
                STATUS
            FROM APPOINTMENTS
            WHERE APPOINTMENT_ID = :appointment_id
        """, {"appointment_id": appointment_id})

        appointment = cursor.fetchone()

        if appointment is None:
            return redirect(
                url_for(
                    "appointments.appointment_list",
                    status="error"
                )
            )

        form_values = {
            "patient_id": str(appointment[1]),
            "doctor_id": str(appointment[2]),
            "appointment_date": appointment[3].strftime("%Y-%m-%d"),
            "appointment_time": format_time_for_input(appointment[4]),
            "status": appointment[5]
        }

        if request.method == "POST":

            form_values = {
                "patient_id": request.form.get("patient_id", "").strip(),
                "doctor_id": request.form.get("doctor_id", "").strip(),
                "appointment_date": request.form.get(
                    "appointment_date", ""
                ).strip(),
                "appointment_time": request.form.get(
                    "appointment_time", ""
                ).strip(),
                "status": request.form.get("status", "").strip()
            }

            patient_id = form_values["patient_id"]
            doctor_id = form_values["doctor_id"]
            date_value = form_values["appointment_date"]
            time_value = form_values["appointment_time"]
            appointment_status = form_values["status"]

            if not all([
                patient_id,
                doctor_id,
                date_value,
                time_value
            ]) or appointment_status not in ALLOWED_STATUSES:

                message = "Please provide valid appointment information."

            else:
                try:
                    patient_id = int(patient_id)
                    doctor_id = int(doctor_id)

                    appointment_date = datetime.strptime(
                        date_value, "%Y-%m-%d"
                    )

                    appointment_time = get_appointment_time(time_value)

                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM PATIENTS
                        WHERE PATIENT_ID = :patient_id
                    """, {"patient_id": patient_id})

                    patient_exists = cursor.fetchone()[0]

                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM DOCTORS
                        WHERE DOCTOR_ID = :doctor_id
                    """, {"doctor_id": doctor_id})

                    doctor_exists = cursor.fetchone()[0]

                    if not patient_exists or not doctor_exists:
                        message = (
                            "Selected patient or doctor does not exist."
                        )

                    else:
                        conflict = None

                        if appointment_status == "Scheduled":
                            conflict = check_appointment_conflict(
                                cursor,
                                patient_id,
                                doctor_id,
                                appointment_date,
                                appointment_time,
                                exclude_appointment_id=appointment_id
                            )

                        if conflict:
                            message = conflict

                        else:
                            try:
                                cursor.execute("""
                                    UPDATE APPOINTMENTS
                                    SET PATIENT_ID = :patient_id,
                                        DOCTOR_ID = :doctor_id,
                                        APPOINTMENT_DATE = :appointment_date,
                                        APPOINTMENT_TIME = :appointment_time,
                                        STATUS = :status
                                    WHERE APPOINTMENT_ID = :appointment_id
                                """, {
                                    "patient_id": patient_id,
                                    "doctor_id": doctor_id,
                                    "appointment_date": appointment_date,
                                    "appointment_time": appointment_time,
                                    "status": appointment_status,
                                    "appointment_id": appointment_id
                                })

                                if cursor.rowcount == 0:
                                    message = "Appointment not found."

                                else:
                                    conn.commit()

                                    return redirect(
                                        url_for(
                                            "appointments.appointment_list",
                                            status="updated"
                                        )
                                    )

                            except oracledb.IntegrityError as error:
                                conn.rollback()
                                message = get_database_conflict_message(error)

                except ValueError:
                    message = "Invalid date, time or ID format."

    except Exception as error:
        if conn:
            conn.rollback()

        print("Edit Appointment Error:", repr(error))
        message = "Unable to update appointment information."

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template(
        "edit_appointment.html",
        appointment=appointment,
        form_values=form_values,
        patients=patients,
        doctors=doctors,
        statuses=ALLOWED_STATUSES,
        message=message,
        message_type=message_type
    )


@appointments_bp.route(
    "/delete/<int:appointment_id>",
    methods=["POST"]
)
def delete_appointment(appointment_id):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM APPOINTMENTS
            WHERE APPOINTMENT_ID = :appointment_id
        """, {"appointment_id": appointment_id})

        if cursor.rowcount == 0:
            return redirect(
                url_for(
                    "appointments.appointment_list",
                    status="error"
                )
            )

        conn.commit()

        return redirect(
            url_for(
                "appointments.appointment_list",
                status="deleted"
            )
        )

    except Exception as error:
        if conn:
            conn.rollback()

        print("Delete Appointment Error:", repr(error))

        return redirect(
            url_for(
                "appointments.appointment_list",
                status="error"
            )
        )

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
