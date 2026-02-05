from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from airflow.sensors.python import PythonSensor
from datetime import datetime
import json
import csv
from docx import Document
import os
from fpdf import FPDF
import time
import pandas as pd
import unicodedata
from textwrap import wrap


def strip_unicode(text):
    if isinstance(text, str):
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 1, 1),
}

def generate_files(**kwargs):
    import json
    import os
    import pandas as pd

    conf = kwargs.get('dag_run').conf or {}
    workspace = conf.get('workspace_name')
    mode = conf.get('mode', 'score')
    output_dir = f"/opt/airflow/data/{workspace}"

    if mode == "combined":
        combined_path = f"{output_dir}/combined_score.json"
        with open(combined_path, "r") as f:
            combined_data = json.load(f)

        contracts = combined_data["raw_combined"]["contracts"]
        final_scores = combined_data.get("final_scores_combined", {})
        summary_of_best = combined_data.get("summary_of_best", {})

        rows = []
        for contract in contracts:
            rows.append({
                "Serial": contract.get("Serial", ""),
                "criterion": contract.get("criterion", ""),
                "name": contract.get("name", ""),
                "score": contract.get("score", ""),
                "rationale": contract.get("rationale", ""),
                "technical_score": contract.get("technical_score", ""),
                "financial_score": contract.get("financial_score", ""),
                "weighted_technical_score": contract.get("weighted_technical_score", ""),
                "weighted_financial_score": contract.get("weighted_financial_score", "")
            })

        df_combined = pd.DataFrame(rows)
        output_excel_path = os.path.join(output_dir, "evaluation_report_combined.xlsx")

        with pd.ExcelWriter(output_excel_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            cell_format = workbook.add_format({'border': 2})
            wrap_format = workbook.add_format({'border': 2, 'text_wrap': True})

            df_combined.to_excel(writer, sheet_name="Combined", index=False)
            worksheet = writer.sheets["Combined"]

            for row_idx, row in enumerate(df_combined.values.tolist(), start=1):
                for col_idx, val in enumerate(row):
                    worksheet.write(row_idx, col_idx, val, wrap_format if df_combined.columns[col_idx] == 'rationale' else cell_format)

            for col_idx, col_name in enumerate(df_combined.columns):
                worksheet.write(0, col_idx, col_name, cell_format)
                max_len = max([len(str(col_name))] + [len(str(val)) for val in df_combined.iloc[:, col_idx].astype(str).values])
                worksheet.set_column(col_idx, col_idx, min(max_len + 2, 60))

        return

    # ✅ For all other modes, just check for existing Excel
    expected_path = os.path.join(output_dir, f"{workspace}_evaluation_report.xlsx")
    if not os.path.exists(expected_path):
        raise FileNotFoundError(f"Expected report file not found at {expected_path}. Please ensure it is generated and uploaded before triggering the DAG.")
    print(f"✅ Found existing report file at: {expected_path}")


    
def check_approval_status(**kwargs):
    conf = kwargs.get('dag_run').conf or {}
    workspace = conf.get("workspace_name")
    status_file = f"/opt/airflow/data/{workspace}/approval_status.txt"
    print(f"🔍 Waiting for approval at: {status_file}")

    timeout = 600  # 10 minutes
    polling_interval = 10
    waited = 0

    while waited < timeout:
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                status = f.read().strip()

                admin_email = conf.get("admin_email", "niraj@allyin.ai")
                from airflow.operators.email import EmailOperator

                if status.lower() in ("approved", "rejected"):
                    subject = f"Your Submission for '{workspace}' was {status.upper()}"
                    message = f"""
                        <html>
                        <body style="font-family: Arial, sans-serif; font-size: 15px; color: #333;">
                            <p>Dear Team,</p>
                            <p>
                            This is to inform you that the contract evaluation submission for the workspace
                            <strong>{workspace}</strong> has been 
                            <span style="color: {'green' if status.lower() == 'approved' else 'red'};">
                                <strong>{status.upper()}</strong>
                            </span>.
                            </p>
                            <p>Thank you for your continued contributions and efforts.</p>
                            <p style="margin-top: 20px;">
                            Regards,<br>
                            <strong>Contract Evaluation System</strong>
                            </p>
                        </body>
                        </html>
                    """

                    EmailOperator(
                        task_id=f"notify_admin_{status.lower()}",
                        to=admin_email,
                        subject=subject,
                        html_content=message,
                        dag=dag
                    ).execute(context=kwargs)

                    os.remove(status_file)
                    if status.lower() == "approved":
                        print("✅ Approved")
                        return
                    else:
                        raise Exception("❌ Rejected by approver")

                elif status.lower().startswith("rfi::"):
                    rfi_message = status[5:].strip()
                    subject = f"RFI Submitted for Workspace '{workspace}'"
                    message = f"""
                        <html>
                        <body style="font-family: Arial, sans-serif; font-size: 15px; color: #333;">
                            <p>Dear Team,</p>
                            <p>
                            A <strong>Request for Improvement (RFI)</strong> has been submitted for the workspace
                            <strong>{workspace}</strong>.
                            </p>
                            <p>
                            <strong>Message:</strong><br>
                            <em>{rfi_message}</em>
                            </p>
                            <p>Please review and take necessary action.</p>
                            <p style="margin-top: 20px;">
                            Regards,<br>
                            <strong>Contract Evaluation System</strong>
                            </p>
                        </body>
                        </html>
                    """

                    EmailOperator(
                        task_id="notify_admin_rfi",
                        to=admin_email,
                        subject=subject,
                        html_content=message,
                        dag=dag
                    ).execute(context=kwargs)

                    os.remove(status_file)
                    raise Exception("📩 RFI submitted by approver.")
        time.sleep(polling_interval)
        waited += polling_interval

    raise TimeoutError("⌛ Approval not received within timeout window.")


def send_to_client(**kwargs):
    print("Simulating final email to client...")  # Replace with EmailOperator if needed

with DAG(
    dag_id="score_to_csv_email_dag",
    default_args=default_args,
    description="Parse JSON score, write CSV + DOCX, wait for approval, and notify client",
    schedule_interval=None,
    catchup=False,
    is_paused_upon_creation=False,
) as dag:

    t1 = PythonOperator(
        task_id="generate_files",
        python_callable=generate_files,
    )
    
    t_send_email = EmailOperator(
        task_id='send_approval_email',
        to='madhur@allyin.ai',
        subject='Approval Required: Contract Score Report',
        html_content="""
            <p style="font-family: Arial, sans-serif; font-size: 15px;">Dear Team,</p>

                <p style="font-family: Arial, sans-serif; font-size: 15px;">
                We have completed the evaluation of the contract submissions for the workspace: 
                <strong>{{ params.workspace_name }}</strong>.
                </p>

                {% if dag_run.conf.get('comment', '') %}
                <p style="font-family: Arial, sans-serif; font-size: 15px;">
                <strong>Note:</strong> {{ dag_run.conf.get('comment', '') }}
                </p>
                {% endif %}

                <p style="font-family: Arial, sans-serif; font-size: 15px;">
                Please review the attached evaluation reports and take action using the buttons below.
                </p>

                <table style="margin: 20px 0;">
                <tr>
                    <td style="padding-right: 10px;">
                    <a href="http://localhost:8000/approve?workspace={{ params.workspace_name }}" 
                        style="font-family: Arial, sans-serif; background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        ✅ Approve
                    </a>
                    </td>
                    <td>
                    <a href="http://localhost:8000/reject?workspace={{ params.workspace_name }}" 
                        style="font-family: Arial, sans-serif; background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        ❌ Reject
                    </a>
                    </td>
                    <td>
                    <a href="http://localhost:8000/rfi?workspace={{ params.workspace_name }}" 
                            style="font-family: Arial, sans-serif; background-color: #ffc107; color: black; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            📝 RFI
                    </a>
                    </td>
                </tr>
                </table>

                <p style="font-family: Arial, sans-serif; font-size: 15px;">
                Thank you for your prompt attention.
                </p>

                <p style="font-family: Arial, sans-serif; font-size: 15px;">
                Regards,<br>
                <strong>Contract Evaluation System</strong>
                </p>
        """,
        files=[
            "{{ '/opt/airflow/data/' ~ params.workspace_name ~ '/evaluation_report_combined.xlsx' if dag_run.conf.get('mode') == 'combined' else '/opt/airflow/data/' ~ params.workspace_name ~ '/' ~ params.workspace_name ~ '_evaluation_report.xlsx' }}"
        ],
        params={
            "workspace_name": "{{ dag_run.conf['workspace_name'] }}"
        },
    )
    
    # t3 = PythonOperator(
    #     task_id="check_approval_status",
    #     python_callable=check_approval_status,
    # )

    # t4 = PythonOperator(
    #     task_id="send_to_client",
    #     python_callable=send_to_client,
    # )
    
   

    t1 >> t_send_email 
    # >> t3 >> t4