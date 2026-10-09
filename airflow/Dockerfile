# Image Airflow officielle + les dépendances du projet.
# On réinstalle "apache-airflow==<version>" dans la même commande pour empêcher pip
# de mettre Airflow à jour (ou de le casser) en résolvant nos dépendances.
FROM apache/airflow:3.3.2

COPY requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir "apache-airflow==3.3.2" -r /requirements-airflow.txt
