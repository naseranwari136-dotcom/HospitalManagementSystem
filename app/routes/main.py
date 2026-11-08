
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template
from database.connection import get_connection

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # Total Patients
        cursor.execute("SELECT COUNT(*) FROM patients")
        total_patients = cursor.fetchone()[0]

        # Total Doctors
        cursor.execute("SELECT COUNT(*) FROM doctors")
        total_doctors = cursor.fetchone()[0]

        # Total Appointments
        cursor.execute("SELECT COUNT(*) FROM appointments")
        total_appointments = cursor.fetchone()[0]

        # Recent Appointments
        cursor.execute("""
            SELECT
                p.full_name,
                d.full_name,
                a.appointment_date,
                a.appointment_time,
                a.status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN doctors d ON a.doctor_id = d.doctor_id
            ORDER BY a.appointment_date DESC,
                     a.appointment_id DESC
            FETCH FIRST 5 ROWS ONLY
        """)

        recent_appointments = cursor.fetchall()

        # Current Week: Saturday to Friday
        today = date.today()

        days_since_saturday = (today.weekday() - 5) % 7

        week_start = today - timedelta(days=days_since_saturday)

        week_end = week_start + timedelta(days=7)

        start_date = datetime.combine(
            week_start, datetime.min.time()
        )

        end_date = datetime.combine(
            week_end, datetime.min.time()
        )

        # Weekly Appointments
        cursor.execute("""
            SELECT TRUNC(appointment_date), COUNT(*)
            FROM appointments
            WHERE appointment_date >= :start_date
              AND appointment_date < :end_date
            GROUP BY TRUNC(appointment_date)
        """,
        start_date=start_date,
        end_date=end_date)

        appointment_rows = cursor.fetchall()

        appointment_data = {
            row[0].date(): row[1]
            for row in appointment_rows
        }

        # Weekly Patient Registrations
        cursor.execute("""
            SELECT TRUNC(created_at), COUNT(*)
            FROM patients
            WHERE created_at >= :start_date
              AND created_at < :end_date
            GROUP BY TRUNC(created_at)
        """,
        start_date=start_date,
        end_date=end_date)

        patient_rows = cursor.fetchall()

        patient_data = {
            row[0].date(): row[1]
            for row in patient_rows
        }

        # Days: Saturday to Friday
        week_days = [
            week_start + timedelta(days=i)
            for i in range(7)
        ]

        # Chart Labels
        chart_labels = [
            day.strftime("%A")
            for day in week_days
        ]

        # Appointments Chart Values
        appointments_chart_values = [
            appointment_data.get(day, 0)
            for day in week_days
        ]

        # Patient Registration Chart Values
        patients_chart_values = [
            patient_data.get(day, 0)
            for day in week_days
        ]

        cursor.close()

    finally:
        conn.close()

    return render_template(
        "dashboard.html",
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        recent_appointments=recent_appointments,
        chart_labels=chart_labels,
        appointments_chart_values=appointments_chart_values,
        patients_chart_values=patients_chart_values
    )
