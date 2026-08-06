import multiprocessing

# L'import de l'interface est volontairement placé sous la garde ci-dessous :
# sous Windows, chaque processus de génération réimporte ce module, et charger
# PySide6 dans les processus enfants coûterait une demi-seconde chacun pour
# rien.
if __name__ == "__main__":
    multiprocessing.freeze_support()

    from app.ui.main_window import run_app

    run_app()
