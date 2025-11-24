import serial
import serial.tools.list_ports
import time
import sys

# --- CONFIGURACIÓN DE LA PRUEBA BER ---
BAUDRATE_OP = 9600       # Velocidad de operación (bps)
SYNC_HEADER = b'\xAA\x55\xAA\x55'
PAYLOAD_SIZE = 64

# --- CONFIGURACIÓN DE COMANDOS AT ---
# (en MHz)
FREQ_LOW  = "430.0000"
FREQ_HIGH = "433.0000"

def detectar_puerto_automatico():
    """Busca puertos FTDI/Raveon automáticamente."""
    ports = list(serial.tools.list_ports.comports())
    candidatos = []
    print("\n--- Buscando Módems Raveon ---")
    for p in ports:
        desc = p.description.upper()
        if "FTDI" in desc or "USB UART" in desc or "FT231X" in desc:
            candidatos.append(p.device)
            print(f" -> ENCONTRADO: {p.device} ({p.description})")
    
    if not candidatos:
        return None
    
    # Selecciona el primero automáticamente o pide confirmación si prefieres
    return candidatos[0]

def abrir_conexion(puerto):
    """Abre el puerto serial con manejo de errores."""
    try:
        # RTS/CTS es importante según el manual para control de flujo
        ser = serial.Serial(puerto, BAUDRATE_OP, timeout=1, rtscts=True)
        return ser
    except serial.SerialException as e:
        if "Permission denied" in str(e):
            print(f"\nERROR DE PERMISOS en {puerto}.")
            print(f"Ejecuta: sudo chmod 666 {puerto}")
        else:
            print(f"\nError abriendo puerto: {e}")
        sys.exit(1)

def esperar_respuesta_ok(ser, timeout=2):
    """Lee el puerto hasta encontrar 'OK' o agotar tiempo."""
    t_end = time.time() + timeout
    resp = b""
    while time.time() < t_end:
        if ser.in_waiting:
            resp += ser.read(ser.in_waiting)
            if b"OK" in resp:
                return True
    return False

def configurar_modem(ser, rol):
    """
    Entra en modo comandos, configura frecuencias y sale.
    Basado en el manual RV-M21 y 'Loading settings'.
    """
    print(f"\n--- INICIANDO CONFIGURACIÓN AUTOMÁTICA ({rol}) ---")
    
    # 1. Entrar en Modo Comandos
    # El manual indica que se requiere silencio antes de la secuencia '+++'
    print("[CFG] Entrando en Modo Comandos (+++)...")
    time.sleep(1.1)  # Silencio previo (>1s según estándar de Raveon)
    ser.write(b"+++")
    time.sleep(1.1)  # Silencio posterior
    
    # Verificar si dió el OK (o si ya estaba en modo comandos)
    # A veces devuelve las letras 'O'o'K' y a veces entra silencioso.
    # Enviamos un AT de prueba para asegurar.
    ser.write(b"AT\r")
    if esperar_respuesta_ok(ser):
        print("[CFG] Módem en Modo Comandos.")
    else:
        print("[CFG] ADVERTENCIA: No se recibió OK inicial. Intentando forzar...")

    # 2. Definir comandos según el rol de TX o RX
    if rol == "A":
        # Módem A: TX en 433 (HIGH), RX en 430 (LOW)
        cmds = [
            f"ATFT {FREQ_HIGH}", # Frecuencia de Transmisión
            f"ATFR {FREQ_LOW}",  # Frecuencia de Recepción
        ]
        info = f"TX={FREQ_HIGH} / RX={FREQ_LOW}"
    else:
        # Módem B: TX en 430 (LOW), RX en 433 (HIGH)
        cmds = [
            f"ATFT {FREQ_LOW}",  # Frecuencia de Transmisión
            f"ATFR {FREQ_HIGH}", # Frecuencia de Recepción
        ]
        info = f"TX={FREQ_LOW} / RX={FREQ_HIGH}"

    # ATMT 0 = Modo Paquetes (Packetized). Es MEJOR para datos que el modo audio (8).
    # ATBD 3 = 9600 baudios (Cambiar según la tabla del manual que nos proporcionó Raveon)
    cmds.extend([
        "ATMT 0", # Modo Paquetes
        "ATBD 3", # 9600 baudios
        "ATRF 0"  # No requerir carrier para sacar datos (útil para pruebas)
    ])

    print(f"[CFG] Aplicando: {info} y Modo Paquetes (9600bps)...")

    # 3. Enviar comandos uno por uno
    for cmd in cmds:
        ser.write(cmd.encode('ascii') + b"\r")
        time.sleep(0.1) # Pequeño delay como sugiere el PDF en "Line Delay"
        if esperar_respuesta_ok(ser):
            print(f"  -> {cmd}: OK")
        else:
            print(f"  -> {cmd}: SIN RESPUESTA (Puede que ya esté configurado)")

    # 4. Salir del Modo Comandos (NECESARIO)
    # El comando suele ser "EXIT".
    print("[CFG] Saliendo del Modo Comandos (EXIT)...")
    ser.write(b"EXIT\r")
    time.sleep(0.5)
    
    # Limpiamos el buffer por si quedaba basura de los comandos
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    print("--- CONFIGURACIÓN COMPLETADA ---\n")

def count_set_bits(n):
    return bin(n).count('1')

def generate_pattern(size):
    return bytes([(i % 256) for i in range(size)])

def modo_transmisor(ser):
    print(f"[TX] Iniciando transmisión de datos...")
    print("[TX] El módem debería estar enviando RF ahora.")
    patron = generate_pattern(PAYLOAD_SIZE)
    trama = SYNC_HEADER + patron
    cnt = 0
    try:
        while True:
            ser.write(trama)
            cnt += 1
            sys.stdout.write(f"\r[TX] Tramas enviadas: {cnt} | Bits: {cnt*len(patron)*8}")
            sys.stdout.flush()
            # Se puede ajustar este time sleep para estresar más el enlace, 
            # pero 0.1s es seguro y está bien para 9600bps.
            time.sleep(0.1) 
    except KeyboardInterrupt:
        print("\n[TX] Detenido.")

def modo_receptor(ser):
    print(f"[RX] Esperando datos...")
    patron_esperado = generate_pattern(PAYLOAD_SIZE)
    total_bits = 0
    error_bits = 0
    pkts = 0
    buffer = b""
    
    try:
        while True:
            if ser.in_waiting:
                buffer += ser.read(ser.in_waiting)
                
                # Procesar buffer buscando cabecera
                while len(buffer) >= len(SYNC_HEADER) + PAYLOAD_SIZE:
                    idx = buffer.find(SYNC_HEADER)
                    if idx == -1:
                        buffer = buffer[-len(SYNC_HEADER):]
                        break
                    if idx > 0:
                        buffer = buffer[idx:]
                        continue # Reevaluar desde el nuevo inicio
                    
                    # Extraer payload
                    payload = buffer[len(SYNC_HEADER):len(SYNC_HEADER)+PAYLOAD_SIZE]
                    if len(payload) < PAYLOAD_SIZE:
                        break # Esperar resto de datos
                    
                    # Calculo de BER
                    errs = 0
                    for b_rx, b_esp in zip(payload, patron_esperado):
                        errs += count_set_bits(b_rx ^ b_esp)
                    
                    error_bits += errs
                    total_bits += (PAYLOAD_SIZE * 8)
                    pkts += 1
                    
                    ber = error_bits / total_bits if total_bits > 0 else 0
                    sys.stdout.write(f"\r[RX] Pkts: {pkts} | Err: {error_bits} | BER: {ber:.6f}")
                    sys.stdout.flush()
                    
                    # Avanzar buffer
                    buffer = buffer[len(SYNC_HEADER)+PAYLOAD_SIZE:]
                    
    except KeyboardInterrupt:
        print("\n\n--- RESULTADO BER ---")
        print(f"Bits Totales: {total_bits}")
        print(f"Bits Error:   {error_bits}")
        print(f"BER Final:    {error_bits/total_bits:.8f}" if total_bits else "N/A")

def main():
    print("=== CONFIGURADOR Y TESTER RAVEON RV-M21 ===")
    
    # 1. Detectar puerto
    puerto = detectar_puerto_automatico()
    if not puerto:
        puerto = input("No se detectó automático. Introduce puerto (ej. /dev/ttyUSB0), o para Windows (ej. COM6): ").strip()
    
    print(f"Usando puerto: {puerto}")
    ser = abrir_conexion(puerto)

    # 2. Preguntar Rol para Configuración
    print("\n¿Qué rol tendrá este módem?")
    print("  A) TX en 433 MHz / RX en 430 MHz")
    print("  B) TX en 430 MHz / RX en 433 MHz")
    print("  X) Saltar configuración (Usar config actual)")
    opcion = input("Selecciona (A/B/X): ").upper()

    if opcion in ["A", "B"]:
        configurar_modem(ser, opcion)
    else:
        print("Saltando configuración de frecuencias...")

    # 3. Iniciar Test BER
    print("\nSelecciona modo de prueba:")
    print("  1) TRANSMISOR (Envía las tramas)")
    print("  2) RECEPTOR   (Calcula BER)")
    modo = input("Opción: ")

    if modo == "1":
        modo_transmisor(ser)
    elif modo == "2":
        modo_receptor(ser)
    
    ser.close()

if __name__ == "__main__":
    main()