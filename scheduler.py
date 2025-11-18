from apscheduler.schedulers.blocking import BlockingScheduler
from downloader import download_latest_netcdf, clean_old_files
from Prediction import run_prediction

sched = BlockingScheduler()

@sched.scheduled_job('interval', minutes=15)
def job():
    print(">> Ejecutando ciclo operativo...")

    # 1. Descargar última imagen
    download_latest_netcdf()
    clean_old_files()

    # 2. Ejecutar predicción
    output_path = run_prediction()
    print("Predicción guardada en:", output_path)


if __name__ == "__main__":
    print("Scheduler iniciado. Ejecutando cada 15 minutos...")
    sched.start()
