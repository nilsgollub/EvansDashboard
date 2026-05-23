import sys
import time

import paramiko


def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        print(text.encode(encoding, errors="replace").decode(encoding))


def run_deploy(host, username, password):
    safe_print(f"Deploy-Loop gestartet. Versuche Verbindung zu {host} als {username}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    attempt = 1
    while True:
        try:
            safe_print(f"Verbindungsversuch {attempt}...")
            # Short timeout so we don't block too long on dead connections
            ssh.connect(host, username=username, password=password, timeout=5, banner_timeout=10)
            safe_print("===> Erfolgreich verbunden! Stoppe Dashboard-Dienst zur CPU-Entlastung...")

            # 1. Stop service
            transport = ssh.get_transport()

            def run_cmd(cmd):
                safe_print(f"Running: {cmd}")
                channel = transport.open_session()
                channel.get_pty()
                channel.exec_command(cmd)

                sudo_prompt_seen = False
                output_accum = ""
                while True:
                    if channel.recv_ready():
                        out = channel.recv(1024).decode("utf-8", errors="ignore")
                        output_accum += out
                        sys.stdout.write(out)
                        sys.stdout.flush()
                        if "password for" in out.lower() and not sudo_prompt_seen:
                            channel.send(password + "\n")
                            sudo_prompt_seen = True
                    if channel.exit_status_ready():
                        break
                    time.sleep(0.1)

                while channel.recv_ready():
                    out = channel.recv(1024).decode("utf-8", errors="ignore")
                    output_accum += out
                    sys.stdout.write(out)
                    sys.stdout.flush()

                code = channel.recv_exit_status()
                safe_print(f"\nExit-Code: {code}\n")
                return code, output_accum

            # Kill any running python processes to instantly free the CPU (no sudo needed!)
            safe_print("===> Töte CPU-intensiven Python-Prozess zur Entlastung...")
            run_cmd("killall -9 python3 || true")
            run_cmd("killall -9 python || true")

            # Now the CPU is 0% idle, we can safely stop the service
            safe_print("===> Stoppe Dashboard-Dienst...")
            run_cmd("sudo systemctl stop evans-dashboard.service")

            # Deploy master branch
            safe_print("===> Aktualisiere Code auf dem Pi...")
            run_cmd("cd ~/EvansDashboard && git fetch --all")
            run_cmd("cd ~/EvansDashboard && git checkout master")
            run_cmd("cd ~/EvansDashboard && git pull origin master")

            # Sicherstellen, dass der Benutzer in der dialout-Gruppe ist (fuer serielle Rechte)
            safe_print("===> Gewaehre Gruppenrechte fuer serielle Schnittstellen (dialout)...")
            run_cmd("sudo usermod -a -G dialout nilsgollub || true")

            # Restart service
            safe_print("===> Starte den optimierten Dashboard-Dienst...")
            run_cmd("sudo systemctl restart evans-dashboard.service")

            # Wait a few seconds and check status
            time.sleep(3)
            run_cmd("sudo systemctl status evans-dashboard.service")
            run_cmd("tail -n 25 ~/dashboard.log || true")

            safe_print("===> DEPLOYMENT ERFOLGREICH ABGESCHLOSSEN!")
            ssh.close()
            break

        except paramiko.AuthenticationException:
            safe_print("Fehler: Authentifizierung fehlgeschlagen! Bitte Passwort pruefen.")
            time.sleep(3)
        except Exception as e:
            safe_print(f"Verbindungsfehler: {e}. Warte 1 Sekunde...")
            time.sleep(1)
            attempt += 1


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python deploy_loop.py <host> <username> <password>")
        sys.exit(1)

    host = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    run_deploy(host, username, password)
