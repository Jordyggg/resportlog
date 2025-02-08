from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from airflow.providers.mysql.hooks.mysql import MySqlHook
from datetime import datetime


# Configuración de MySQL
INDEX_NAME = "network_logs"
MYSQL_CONN_ID = "mysql_default"


# Función para conectar a la base de datos 
def connect_template_db(database):
    mysql_hook = MySqlHook(mysql_conn_id=database)
    connection = mysql_hook.get_conn()
    cursor = connection.cursor()
    return cursor, connection

def extract_logs(ti):
    cursor,connection = connect_template_db("mysql_default")
    cursor.execute("SELECT * FROM network_logs")
    connection.commit()
    logs = cursor.fetchall()
    cursor.close()
    connection.close()
    print(logs)
    # Enviar logs extraídos a XCom para ser utilizados en otro DAG
    ti.xcom_push(key="logs", value=logs)



def procesar_logs_restart(**kwargs):
    # Obtener los logs desde XCom
    logs = kwargs['ti'].xcom_pull(task_ids='extraer_logs', key='logs')
    print("Logs completos:", logs)

    # Filtrar logs que contienen 'RESTART'
    restart_logs = [log for log in logs if 'RESTART' in log[2]]
    print("Logs con RESTART:", restart_logs)

    # Contar los equipos que tienen 'RESTART'
    equipos_restart = {}
    for log in restart_logs:
        equipo = log[2].split(' ')[1]  # Asumiendo que el nombre del equipo es la segunda palabra
        equipos_restart[equipo] = equipos_restart.get(equipo, 0) + 1
    print(equipos_restart)

    # Contar el número total de equipos con 'RESTART'
    restart_count = len(equipos_restart)
    print("Total de equipos con RESTART:", restart_count)

    # Validación si hay equipos reiniciados
    if equipos_restart:
        # Obtener el equipo con más reinicios
        top_1_equipos = sorted(equipos_restart.items(), key=lambda x: x[1], reverse=True)[0]
        print("Equipo con más reinicio:", top_1_equipos)
    else:
        top_1_equipos = ("Ninguno", 0)  # Valor por defecto si no hay equipos reiniciados
        print("No hay equipos con reinicios.")

    # Crear un diccionario con los resultados
    resultado = {
        "restart_logs": restart_logs,
        "total_equipos_reiniciados": restart_count,
        "top_equipos": top_1_equipos
    }

    # Enviar los resultados a XCom
    kwargs['ti'].xcom_push(key='restart_data', value=resultado)

    # Imprimir el reporte para verificación
    print("Resultado:", resultado)


def procesar_logs_unavailability(**kwargs):
    logs = kwargs['ti'].xcom_pull(task_ids='extraer_logs', key='logs')
    print("Logs completos:", logs)

    # Filtrar logs que contienen 'unavailably by ICMP'
    unavailable_logs = [(log[1], log[2]) for log in logs if "unavailably by ICMP" in log[2]]
    print("Logs con 'unavailably by ICMP':", unavailable_logs)

    # Crear un diccionario para contar las caídas de cada equipo
    equipos_caidos = {}
    for log in unavailable_logs:
        fecha_caida, mensaje_caida = log
        
        # Extraer nombre del equipo y la IP
        partes = mensaje_caida.split()
        equipo = partes[3]  # El nombre del equipo es la tercera palabra
        ip = partes[4]  # La IP es la cuarta palabra
        print(equipo)
        print(ip)
        # Contar las caídas de cada equipo
        if equipo not in equipos_caidos:
            equipos_caidos[equipo] = {"ip": ip, "caidas": 0, "fechas": []}
        equipos_caidos[equipo]["caidas"] += 1
        equipos_caidos[equipo]["fechas"].append(fecha_caida)

    # Identificar el equipo con más caídas
    equipo_mas_caidas = max(equipos_caidos.items(), key=lambda x: x[1]["caidas"], default=None)

    # Generar el reporte en formato string
    reporte = f"\nReporte de caídas de equipos (unavailably by ICMP)\n\n"
    reporte += "Equipo | IP | Timestamp de caída | Número de caídas\n"
    reporte += "-" * 80 + "\n"
    
    for equipo, datos in equipos_caidos.items():
        ip = datos["ip"]
        caidas = datos["caidas"]
        
        # Convertir las fechas a cadenas de texto antes de unirlas
        fechas = ", ".join([fecha.strftime("%Y-%m-%d %H:%M:%S") for fecha in datos["fechas"]])
        
        reporte += f"{equipo} | {ip} | {fechas} | {caidas}\n"
    
    if equipo_mas_caidas:
        reporte += f"\nEquipo con más caídas: {equipo_mas_caidas[0]} con {equipo_mas_caidas[1]['caidas']} caídas.\n"

    # Crear un diccionario con los resultados
    resultado = {
        "equipos caidos": equipos_caidos,
        "reporte": reporte,
        "total_equipos_caidos": len(equipos_caidos),
        "equipo_mas_caidas": equipo_mas_caidas
    }

    # Enviar los resultados a XCom
    kwargs['ti'].xcom_push(key='unavailability_data', value=resultado)

    # Imprimir el reporte para verificación
    print(reporte)
    print(equipos_caidos)


# Función para procesar logs con "up" y "down"
def procesar_logs_up_down(**kwargs):
    logs = kwargs['ti'].xcom_pull(task_ids='extraer_logs', key='logs')

    # Filtrar logs con "down" (caída de interfaz)
    down_logs = [(log[1], log[2]) for log in logs if "down" in log[2]]
    
    # Filtrar logs con "up" (activación de interfaz)
    up_logs = [(log[1], log[2]) for log in logs if "up" in log[2]]

    # Generar el reporte para los logs "down"
    reporte_down = f"Reporte de caídas de interfaces (down)\n\n"
    reporte_down += "Timestamp de caída | Mensaje\n"
    reporte_down += "-" * 80 + "\n"
    
    for timestamp, message in down_logs:
        reporte_down += f"{timestamp} | {message}\n"

    # Generar el reporte para los logs "up"
    reporte_up = f"Reporte de activaciones de interfaces (up)\n\n"
    reporte_up += "Timestamp de activación | Mensaje\n"
    reporte_up += "-" * 80 + "\n"
    
    for timestamp, message in up_logs:
        reporte_up += f"{timestamp} | {message}\n"

    # Crear un diccionario con los reportes
    reportes = {
        "reporte_down": reporte_down,
        "reporte_up": reporte_up
    }

    # Enviar los reportes a XCom
    kwargs['ti'].xcom_push(key='interface_reports', value=reportes)

    # Imprimir los reportes para verificación
    print(reporte_down)
    print(reporte_up)



def generar_reporte(**kwargs):
    # Obtener los datos procesados de las tareas anteriores desde XCom
    restart_data = kwargs['ti'].xcom_pull(task_ids='procesar_logs_restart', key='restart_data')
    unavailability_data = kwargs['ti'].xcom_pull(task_ids='procesar_logs_unavailability', key='unavailability_data')
    interface_changes = kwargs['ti'].xcom_pull(task_ids='procesar_logs_up_down', key='interface_reports')
    print(restart_data)
    print(unavailability_data)
    print(interface_changes)

    # Conectar a la base de datos de clientes
    cursor, connection = connect_template_db("mysql_default1")
    
    # Consultar los datos de switches y clientes desde la base de datos
    cursor.execute("SELECT switch_name, client_name FROM switches_y_clientes")
    connection.commit()
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    # Convertir los datos a un formato adecuado (diccionario de clientes extraido de una base sql)
    switches_clientes_dict = {}
    for row in rows:
        switch_name, cliente = row
        if switch_name not in switches_clientes_dict:
            switches_clientes_dict[switch_name] = []
        switches_clientes_dict[switch_name].append(cliente)

    print(switches_clientes_dict)
    # Crear el diccionario para los resultados
    resultado = {}


    switches_caidos = unavailability_data['equipos caidos'].keys()

    #  Crear el reporte
    report ="Reporte de Clientes  Caídos:**\n"
    report+="="*50  # Línea divisoria
    report+=f"{'Switch Caído':<20} {'Cliente'}\n"
    report+="="*50

    for switch in switches_caidos:
        if switch in switches_clientes_dict:
            for cliente in switches_clientes_dict[switch]:
                print(f"{switch:<20} {cliente}")
                report+="\n"+switch+"    "+cliente+"\n"

    # Procesar reporte de reinicios
    restart_logs = restart_data["restart_logs"]
    restart_count = restart_data["total_equipos_reiniciados"]
    top_1_equipos = restart_data["top_equipos"]

    resultado['restart_logs'] = restart_logs
    resultado['total_equipos_reiniciados'] = restart_count
    resultado['top_equipos'] = top_1_equipos

    # Procesar interfaces up/down
    reporte_down = interface_changes["reporte_down"]
    reporte_up = interface_changes["reporte_up"]
    reportes = {
        "reporte_down": reporte_down,
        "reporte_up": reporte_up
    }

    # Crear el reporte final
    report += "📌 **Reporte de caídas de equipos:**\n"
    #for entry in resultado['reporte']:
    #    report += entry + "\n"
    print(unavailability_data['reporte'])
    report+=unavailability_data['reporte']

    # Añadir reporte de reinicios
    report += "\n📌 **Reporte de reinicios:**\n"
    report += f"🔹 Total de equipos reiniciados: {resultado['total_equipos_reiniciados']}\n"
    report += f"🔹 Top 1 equipo con más reinicios: {resultado['top_equipos'][0]} ({resultado['top_equipos'][1]})\n"

    # Añadir reporte de reinicios con lista de logs detallada
    report += "\n📌 **Detalle de logs de reinicios:**\n"
    for log_entry in restart_logs:
        log_id, timestamp, message = log_entry  # Extraer valores
        report += f"🔹 ID: {log_id} | Timestamp: {timestamp} | Mensaje: {message}\n"
    # Añadir reporte de interfaces caídas y activaciones
    # Añadir reporte de interfaces caídas
    report += "\n📌 **Reporte de interfaces caídas:**\n"
    report += reportes["reporte_down"] + "\n"

    # Añadir reporte de interfaces activadas
    report += "\n📌 **Reporte de interfaces activadas:**\n"
    report += reportes["reporte_up"] + "\n"

    try:
    # Guardar el reporte en la base de datos MySQL
        cursor,connection = connect_template_db("mysql_default")
        cursor.execute("""
        INSERT INTO consolidated_reports (report, created_at)
        VALUES (%s, NOW())
        """, (report,))
        connection.commit()
        connection.close()
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error al insertar el reporte: {e}")

    # Enviar el reporte por correo
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "jggarzonbsc@gmail.com"
    sender_password = "btmw kdlx tpkb phmq"  # Usa una variable de entorno para las contraseñas por seguridad
    recipient_email = "garzonjordy@hotmail.com"

    msg = MIMEText(report, "plain", "utf-8")
    msg["Subject"] = "INFORME DE EVENTOS EN LA RED DE BACKBONE - AIRFLOW 📊"
    msg["From"] = sender_email
    msg["To"] = recipient_email

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Error enviando el correo: {e}")


# Definir DAG y tareas
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 2, 7),
    'retries': 1,
}

dag = DAG('Incident_Report_Generation', default_args=default_args, schedule_interval=None, catchup=False)

pull_data = PythonOperator(task_id='extraer_logs', python_callable=extract_logs, dag=dag)
filtering_restart = PythonOperator(task_id='procesar_logs_restart', python_callable=procesar_logs_restart, dag=dag)
filtering_down = PythonOperator(task_id='procesar_logs_unavailability', python_callable=procesar_logs_unavailability, dag=dag)
filtering_interface = PythonOperator(task_id='procesar_logs_up_down', python_callable=procesar_logs_up_down, dag=dag)
report = PythonOperator(task_id='generar_reporte', python_callable=generar_reporte, dag=dag)

pull_data >> [filtering_restart, filtering_down, filtering_interface] >> report
