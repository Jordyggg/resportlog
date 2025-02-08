# resportlog

**Monitoreo del logs de red de networking PYTHON + ELK + AIRFLOW.**

Capturar logs de un servidor de monitoreo de redes de backbone y emitir un reporte final


El proyecto consiste en implementar un sistema que extraiga los logs que describen los eventos de una red de Networking en un entorno Near Real Time. De esa manera procesarlos para generar respectivos reportes sobre las incidencias en la red de backbone.
![imagen](https://github.com/user-attachments/assets/3ffe8cc9-6264-47b8-9ae7-d02af569551f)

notas.
-- docker-compose son los contenedores docker correspondientes a Airflow.
-- datafake.ipynb genera los logs de red para ser procesados esto es en tiempo real en el proceso de cada 2 seg, los mismos logs son enviados a elastisearch.
-- Incident_Report_Generation.py flujo de trabajo DAG airflow que se encarga de procesar los datos y generar reportes.
-- docker-comose_elk.yml es el docer de ELK debe ser ejecutado en otra carpeta.
